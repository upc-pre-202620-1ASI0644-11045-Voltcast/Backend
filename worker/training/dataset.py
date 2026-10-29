"""Anchor, normalized target and forecast origins, ported from the PoC (src/voltcast/dataset.py)."""
import numpy as np
import pandas as pd
import torch

from worker.training import config

FEATURES = ["v_rel", "kA_z", "vcel_z", "mascara"]


def anchor(vf: pd.DataFrame, days: int = config.ANCHOR_DAYS) -> pd.DataFrame:
    """Recent level of each cell: mean of the last `days` days of the filtered signal (all of them are required)."""
    return vf.rolling(days, min_periods=days).mean()


def origin_ok(anc: pd.DataFrame, oos: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """An origin is usable when it has an anchor and its input window does not touch an out-of-service stretch."""
    touches_oos = oos.astype(float).rolling(lookback, min_periods=1).max().astype(bool)
    return anc.notna() & ~touches_oos


def delta_sigma(v_real: pd.DataFrame, objective: pd.DataFrame, anc: pd.DataFrame, ok_t0: pd.DataFrame,
                horizon: int = config.HORIZON_DAYS) -> float:
    """Global standard deviation of V_real(t0 + h) - anchor(t0) over h = 1..horizon: the scale of the normalized target."""
    V = np.where(objective.to_numpy(), v_real.to_numpy(), np.nan)
    A = np.where(ok_t0.to_numpy(), anc.to_numpy(), np.nan)
    n_tot, s_tot, ss_tot = 0, 0.0, 0.0
    for h in range(1, horizon + 1):
        d = V[h:] - A[:-h]
        d = d[np.isfinite(d)]
        n_tot, s_tot, ss_tot = n_tot + d.size, s_tot + float(d.sum()), ss_tot + float((d ** 2).sum())
    if n_tot == 0:
        return float("nan")
    return float(np.sqrt(max(ss_tot / n_tot - (s_tot / n_tot) ** 2, 0.0)))


def next_jump_index(dates: pd.DatetimeIndex, cells: list[str], shifts: pd.DataFrame) -> np.ndarray:
    """`[T, C]`: index of the next level shift after each date for each cell; `2T` when there is none."""
    T, pos = len(dates), {d: i for i, d in enumerate(dates)}
    nxt = np.full((T, len(cells)), 2 * T, dtype=np.int64)
    for j, c in enumerate(cells):
        for k in sorted((pos[d] for d in shifts.loc[shifts["celda"] == c, "fecha"] if d in pos), reverse=True):
            nxt[:k, j] = k
    return nxt


def build_inputs(vf_win, valid_win, ka_win, vcel_win, sigma: float, anchor_days: int = config.ANCHOR_DAYS):
    """Windows `[N, L]` -> (input `[N, L, 4]`, anchor `[N]`): filtered voltage relative to the anchor / sigma, kA, V per cell, quality."""
    anc = vf_win[:, -anchor_days:].mean(dim=1)
    v_rel = (vf_win - anc[:, None]) / sigma
    x = torch.stack([v_rel, torch.nan_to_num(ka_win), torch.nan_to_num(vcel_win), valid_win.float()], dim=-1)
    return x, anc


class SeriesTensors:
    """Daily series of every cell and assembly of (cell, origin) batches without materializing the windows."""

    def __init__(self, p, sigma: float, lookback: int = config.LOOKBACK_DAYS, horizon: int = config.HORIZON_DAYS):
        def t(frame, dtype=torch.float32):
            return torch.tensor(frame.to_numpy(dtype=float), dtype=dtype)

        self.cells, self.sigma, self.L, self.H, self.device = p.cells, sigma, lookback, horizon, "cpu"
        self.dates = p.dates
        self.VF, self.V, self.KA, self.VC = t(p.vf), t(p.v), t(p.ka), t(p.vc)
        self.VALID, self.OBJ, self.OOS = t(p.valid).bool(), t(p.obj).bool(), t(p.oos).bool()
        self.el_flag = torch.tensor([float(c[0] == "B") for c in p.cells])
        # Usable origins: complete filtered window and no out-of-service day in it (so the anchor is defined)
        vf_ok = pd.DataFrame(np.isfinite(p.vf.to_numpy(float)))
        oos = pd.DataFrame(p.oos.to_numpy(float))
        ok = (vf_ok.rolling(lookback, min_periods=lookback).min() == 1) & (oos.rolling(lookback, min_periods=1).max() == 0)
        self.ok = torch.tensor(ok.to_numpy())
        self.offs_in = torch.arange(-lookback + 1, 1)
        self.offs_out = torch.arange(1, horizon + 1)
        self.next_jump = None

    def set_level_shifts(self, shifts: pd.DataFrame) -> None:
        """For each (t, cell), the index of the next level shift after t: the targets from it on are ignored in training."""
        self.next_jump = torch.tensor(next_jump_index(self.dates, self.cells, shifts))

    def origins(self, t_min: int, t_max: int, stride: int = 1, phase: int = 0):
        """Usable (cell, t) pairs with `t_min <= t <= t_max` and `(t - phase) % stride == 0`."""
        ok = self.ok.clone()
        ok[:t_min] = False
        ok[t_max + 1:] = False
        t_idx = torch.arange(len(self.dates))
        ok &= ((t_idx - phase) % stride == 0)[:, None]
        t, c = torch.nonzero(ok, as_tuple=True)
        return c, t

    def batch(self, c, t, target_limit: int, mask_jumps: bool = False):
        """Inputs and targets of a batch. Targets after `target_limit` (a date index) are masked, and with `mask_jumps` so are
        the ones from the cell's next level shift on."""
        win = t[:, None] + self.offs_in
        cc = c[:, None]
        x, anc = build_inputs(self.VF[win, cc], self.VALID[win, cc], self.KA[win, cc], self.VC[win, cc], self.sigma)
        tgt = t[:, None] + self.offs_out
        inside = tgt <= min(target_limit, len(self.dates) - 1)
        tgt = tgt.clamp(max=len(self.dates) - 1)
        y = (self.V[tgt, cc] - anc[:, None]) / self.sigma
        mask = inside & self.OBJ[tgt, cc] & torch.isfinite(y)
        if mask_jumps:
            mask &= tgt < self.next_jump[t, c][:, None]
        return x, torch.nan_to_num(y), mask, c, self.el_flag[c]
