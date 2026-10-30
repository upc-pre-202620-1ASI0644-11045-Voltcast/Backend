"""VMD filtering of the voltage series, ported from the PoC (src/voltcast/vmd.py), without the parameter search."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from vmdpy import VMD

from worker.etl.cleaning import true_runs
from worker.training import config

TAU, DC, INIT, TOL = 0.0, 0, 1, 1e-6  # vmdpy settings the PoC validated

_PARAMS_FILE = Path(__file__).with_name("vmd_params.json")


def load_vmd_params() -> tuple[dict[str, tuple[int, float]], tuple[int, float]]:
    """
    (K, alpha) per cell found by the Bayesian search of the PoC, and the most frequent pair for the cells it did not
    cover. The search is not repeated here: 298 of the 300 cells ended with the same pair.
    """
    data = json.loads(_PARAMS_FILE.read_text(encoding="utf-8"))
    per_cell = {r["celda"]: (int(r["K"]), float(r["alpha"])) for r in data["por_celda"]}
    return per_cell, Counter(per_cell.values()).most_common(1)[0][0]


def fill_gaps(x: np.ndarray) -> np.ndarray:
    """Linear interpolation of the inner NaNs and constant fill at the ends (only to feed the VMD)."""
    x = np.asarray(x, dtype=float)
    ok = ~np.isnan(x)
    if ok.all() or not ok.any():
        return x.copy()
    idx = np.arange(len(x))
    return np.interp(idx, idx[ok], x[ok])


def decompose(x: np.ndarray, K: int, alpha: float) -> np.ndarray:
    """
    VMD modes `[K, len(x)]` sorted by increasing center frequency. vmdpy drops the last sample of an odd-length
    series; here the first one is dropped (left as NaN) so the most recent end is kept, which the causal filter needs.
    """
    x = np.asarray(x, dtype=float)
    off = len(x) % 2
    u, _, omega = VMD(x[off:], alpha, TAU, int(K), DC, INIT, TOL)
    u = u[np.argsort(omega[-1])]
    if off:
        u = np.hstack([np.full((u.shape[0], 1), np.nan), u])
    return u


def vmd_filter(x: np.ndarray, K: int, alpha: float, n_drop: int = config.VMD_N_DROP) -> np.ndarray:
    """The series rebuilt without its `n_drop` highest-frequency modes."""
    return decompose(fill_gaps(x), K, alpha)[: K - n_drop].sum(axis=0)


def _segments(blocked: np.ndarray) -> list[tuple[int, int]]:
    return true_runs(~np.asarray(blocked, dtype=bool))


def filter_segments(x: np.ndarray, blocked: np.ndarray, K: int, alpha: float, min_len: int = config.VMD_MIN_LEN) -> np.ndarray:
    """Filters each in-service stretch (not `blocked`) of at least `min_len` days; everything else stays NaN."""
    out = np.full(len(x), np.nan)
    for a, b in _segments(blocked):
        seg = x[a:b + 1]
        if b - a + 1 >= min_len and np.isfinite(seg).sum() >= min_len // 2:
            out[a:b + 1] = vmd_filter(seg, K, alpha)
    return out


def causal_window(x: np.ndarray, blocked: np.ndarray, t0: int, K: int, alpha: float,
                  history: int = config.VMD_HISTORY, lookback: int = config.LOOKBACK_DAYS,
                  min_len: int = config.VMD_MIN_LEN) -> np.ndarray:
    """
    Filtered signal of the last `lookback` days up to `t0`, using only the `history` days before it and the in-service
    stretch that ends at `t0`. NaN when `t0` is blocked or that stretch is shorter than `min_len`.
    """
    out = np.full(lookback, np.nan)
    a = max(0, t0 - history + 1)
    blk = np.asarray(blocked[a:t0 + 1], dtype=bool)
    if blk[-1]:
        return out
    ini = a + (np.where(blk)[0].max() + 1 if blk.any() else 0)
    seg = x[ini:t0 + 1]
    if len(seg) < min_len or np.isfinite(seg).sum() < min_len // 2:
        return out
    u = decompose(fill_gaps(seg), K, alpha)
    return u[: K - config.VMD_N_DROP, -lookback:].sum(axis=0)
