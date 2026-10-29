"""The Bi-LSTM of the PoC (src/voltcast/model.py): one cell per sample, weights shared by every cell."""
import copy

import torch
from torch import Tensor, nn

from worker.training import config


class VoltCastNet(nn.Module):
    """
    Window `[B, L, F]` of one cell -> `[B, H]` normalized forecast: concat(final state of a bidirectional LSTM,
    cell embedding, electrolyzer flag) -> Linear -> ReLU -> Linear(H), with no output activation.
    """

    def __init__(self, n_cells: int, n_features: int, hidden: int = 64, layers: int = 1, emb_dim: int = 8,
                 head_hidden: int = 256, horizon: int = config.HORIZON_DAYS, dropout: float = 0.2):
        super().__init__()
        self.encoder = nn.LSTM(n_features, hidden, num_layers=layers, batch_first=True, bidirectional=True,
                               dropout=dropout if layers > 1 else 0.0)
        self.emb = nn.Embedding(n_cells, emb_dim)
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(2 * hidden + emb_dim + 1, head_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, horizon),
        )

    def forward(self, x: Tensor, cell: Tensor, el_flag: Tensor) -> Tensor:
        _, (h_n, _) = self.encoder(x)
        z = torch.cat([h_n[-2], h_n[-1], self.emb(cell), el_flag.unsqueeze(-1)], dim=-1)
        return self.head(z)


MODEL_KWARGS = ["hidden", "layers", "emb_dim", "head_hidden", "dropout"]


def build_model(n_cells: int, n_features: int, cfg: dict) -> VoltCastNet:
    return VoltCastNet(n_cells, n_features, **{k: cfg[k] for k in MODEL_KWARGS})


def masked_mse(pred: Tensor, y: Tensor, mask: Tensor) -> Tensor:
    m = mask.float()
    return ((pred - y) ** 2 * m).sum() / m.sum().clamp(min=1.0)


def run_epoch(model, data, c, t, target_limit: int, batch_size: int, opt=None, clip: float | None = None,
              generator=None, mask_jumps: bool = False) -> float:
    """One pass over the (cell, origin) pairs: trains with `opt`, evaluates without it. Returns the normalized MSE."""
    train = opt is not None
    model.train(train)
    n = len(t)
    order = torch.randperm(n, device=t.device, generator=generator) if train else torch.arange(n, device=t.device)
    se, cnt = 0.0, 0
    with torch.set_grad_enabled(train):
        for i in range(0, n, batch_size):
            idx = order[i:i + batch_size]
            x, y, mask, cell, el = data.batch(c[idx], t[idx], target_limit, mask_jumps)
            loss = masked_mse(model(x, cell, el), y, mask)
            k = int(mask.sum())
            if train:
                opt.zero_grad(set_to_none=True)
                loss.backward()
                if clip:
                    nn.utils.clip_grad_norm_(model.parameters(), clip)
                opt.step()
            se += float(loss.detach()) * k
            cnt += k
    return se / max(cnt, 1)


def fit(model, data, train_range: tuple[int, int], train_target_limit: int, cfg: dict, val_pairs=None,
        val_target_limit: int | None = None, epochs: int | None = None, seed: int = config.SEED,
        mask_jumps: bool = True, log=None) -> dict:
    """
    Trains on origins subsampled every `cfg['stride']` days (random phase each epoch). With `val_pairs` it stops early
    (`cfg['patience']`) and restores the best weights; without them it trains exactly `epochs` epochs.
    """
    gen = torch.Generator(device=data.device).manual_seed(seed)
    rng = torch.Generator().manual_seed(seed)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    max_ep = epochs or cfg["max_epochs"]
    best, best_state, best_ep, wait = float("inf"), None, 0, 0
    for ep in range(1, max_ep + 1):
        phase = int(torch.randint(cfg["stride"], (1,), generator=rng))
        c, t = data.origins(*train_range, stride=cfg["stride"], phase=phase)
        train_mse = run_epoch(model, data, c, t, train_target_limit, cfg["batch_size"], opt, cfg.get("clip"), gen, mask_jumps)
        if val_pairs is not None:
            val_mse = run_epoch(model, data, *val_pairs, val_target_limit, cfg["batch_size"] * 4, mask_jumps=mask_jumps)
            if val_mse < best - 1e-5:
                best, best_ep, wait = val_mse, ep, 0
                best_state = copy.deepcopy(model.state_dict())
            else:
                wait += 1
            if log:
                log(f"epoch {ep}: train_mse {train_mse:.4f} val_mse {val_mse:.4f}")
            if wait >= cfg["patience"]:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return {"best_epoch": best_ep or max_ep}
