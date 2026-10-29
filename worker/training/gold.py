"""Gold layer: filtered signal, covariates and scale of the target, ported from the PoC notebook 05 (all days are training days)."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from worker.etl.cleaning import CALIDAD
from worker.training import config
from worker.training import vmd
from worker.training.dataset import anchor, delta_sigma, origin_ok


class TrainingDataError(ValueError):
    """The data cannot train a model; the message says why."""


@dataclass
class Prepared:
    dates: pd.DatetimeIndex
    cells: list[str]
    v: pd.DataFrame  # measured voltage (Silver)
    vf: pd.DataFrame  # filtered voltage
    ka: pd.DataFrame  # kA, standardized
    vc: pd.DataFrame  # voltage per in-service cell, standardized
    valid: pd.DataFrame
    obj: pd.DataFrame
    oos: pd.DataFrame
    codes: pd.DataFrame  # quality codes, to detect level shifts
    params: dict[str, tuple[int, float]]  # VMD (K, alpha) of each cell
    sigma: float
    covariates: dict  # mean and deviation used to standardize kA and the voltage per cell


def _pivot(silver: pd.DataFrame, value: str, cells: list[str]) -> pd.DataFrame:
    w = silver.pivot(index="fecha", columns="celda", values=value)
    w.columns = w.columns.astype(str)
    return w[cells]


def _standardize(values: pd.Series, mask: pd.Series, stats: dict | None = None) -> tuple[pd.Series, dict]:
    """z-score clipped to +-COV_CLIP, with mean and deviation taken from the days of `mask` (no shutdowns) unless `stats` is given."""
    if stats is None:
        mean, std = float(values[mask].mean()), float(values[mask].std())
        stats = {"media": mean, "desvio": std if np.isfinite(std) and std > 0 else 1.0}
    return ((values - stats["media"]) / stats["desvio"]).clip(-config.COV_CLIP, config.COV_CLIP), stats


def covariates_z(silver: pd.DataFrame, cells: list[str], dates: pd.DatetimeIndex,
                 stats: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    kA and voltage per in-service cell of each section, standardized and spread over its cells (`[dates, cells]`).
    `stats` fixes the mean and deviation (the ones of the training days) instead of fitting them to these days.
    """
    cov = silver.groupby(["fecha", "electrolizador"], observed=True)[["kA", "V_total", "n_en_servicio"]].first().reset_index()
    cells_per_section = silver.groupby("electrolizador", observed=True)["celda"].nunique()
    extra = config.PHYSICAL_CELLS_PER_ELECTROLYZER - cov["electrolizador"].map(cells_per_section).astype(int)
    cov["V_celda_media"] = cov["V_total"] / (cov["n_en_servicio"] + extra)
    running = cov["kA"] >= config.KA_SHUTDOWN
    cov["kA_z"], ka_stats = _standardize(cov["kA"], running, stats and stats["kA"])
    cov["vcel_z"], vc_stats = _standardize(cov["V_celda_media"], running, stats and stats["V_celda_media"])
    z = {name: cov.pivot(index="fecha", columns="electrolizador", values=name).reindex(dates) for name in ("kA_z", "vcel_z")}
    ka = pd.DataFrame({c: z["kA_z"][c[0]] for c in cells})
    vc = pd.DataFrame({c: z["vcel_z"][c[0]] for c in cells})
    return ka, vc, {"kA": ka_stats, "V_celda_media": vc_stats}


def prepare(silver: pd.DataFrame, n_jobs: int = -1) -> Prepared:
    cells = sorted(silver["celda"].astype(str).unique())
    quality = _pivot(silver, "calidad", cells).astype(str)
    v = _pivot(silver, "voltaje", cells)
    dates = v.index
    oos = quality == "fuera_servicio"

    per_cell, default = vmd.load_vmd_params()
    params = {c: per_cell.get(c, default) for c in cells}
    filtered = Parallel(n_jobs=n_jobs)(
        delayed(vmd.filter_segments)(v[c].to_numpy(), oos[c].to_numpy(), *params[c]) for c in cells
    )
    vf = pd.DataFrame(np.column_stack(filtered), index=dates, columns=cells)

    ka, vc, covariates = covariates_z(silver, cells, dates)

    anc = anchor(vf)
    sigma = delta_sigma(v, quality == "ok", anc, origin_ok(anc, oos, config.SIGMA_LOOKBACK_DAYS))
    if not np.isfinite(sigma) or sigma <= 0:
        raise TrainingDataError("The data has no in-service stretch long enough to learn from")

    return Prepared(
        dates=dates, cells=cells, v=v, vf=vf, ka=ka, vc=vc,
        valid=quality.isin(["ok", "interpolado"]), obj=quality == "ok", oos=oos,
        codes=quality.apply(lambda s: pd.Categorical(s, categories=CALIDAD).codes), params=params, sigma=sigma,
        covariates=covariates,
    )
