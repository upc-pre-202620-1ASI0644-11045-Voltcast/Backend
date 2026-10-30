from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pandas as pd
import torch
from joblib import Parallel, cpu_count, delayed

from worker.etl.cleaning import level_shifts
from worker.training import config, vmd
from worker.training.dataset import FEATURES, SeriesTensors, build_inputs
from worker.training.gold import Prepared, TrainingDataError, covariates_z, prepare
from worker.training.model import build_model, fit


@dataclass
class TrainingResult:
    checkpoint: bytes  # weights and everything needed to rebuild and read the model
    scalers: dict
    predictions: pd.DataFrame  # celda, fecha, voltaje: the next HORIZON_DAYS days after the last day of the data
    evaluation: pd.DataFrame  # celda, fecha, predicho, real: a backtest forecast against the measured voltage
    metrics: dict  # rmse, mae, mape (percentage), r2 over every forecast of the validation days
    best_epoch: int


def _limit_threads() -> None:
    """torch counts the host cores, not the CPU quota of the container, and would oversubscribe it; joblib does respect the quota."""
    torch.set_num_threads(max(1, min(torch.get_num_threads(), cpu_count())))


def _causal_windows(p: Prepared, origins: list[int], n_jobs: int) -> np.ndarray:
    """Filtered signal `[O, C, L]` of the last days up to each origin, using only data until that origin."""
    rows = Parallel(n_jobs=n_jobs)(
        delayed(vmd.causal_window)(p.v[c].to_numpy(), p.oos[c].to_numpy(), t0, *p.params[c]) for t0 in origins for c in p.cells
    )
    return np.stack(rows).reshape(len(origins), len(p.cells), config.LOOKBACK_DAYS)


@torch.no_grad()
def _forecast(model, p: Prepared, ka: pd.DataFrame, vc: pd.DataFrame, sigma: float, origins: list[int],
              n_jobs: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Per origin: the voltage forecast `[N, H]` of the cells whose window is complete, and their indexes. `ka` and `vc` are
    the covariates standardized the way the model was trained, `sigma` the scale of its target.
    """
    L = config.LOOKBACK_DAYS
    windows = _causal_windows(p, origins, n_jobs)
    out = []
    for vf_win, t0 in zip(windows, origins):
        rows = np.where(np.isfinite(vf_win).all(axis=1))[0]
        if rows.size == 0:
            out.append((np.empty((0, config.HORIZON_DAYS)), rows))
            continue
        sl = slice(t0 - L + 1, t0 + 1)

        def window(frame: pd.DataFrame, dtype=torch.float32):
            return torch.as_tensor(frame.iloc[sl, rows].to_numpy(dtype=float, copy=True).T, dtype=dtype)

        x, anc = build_inputs(torch.as_tensor(vf_win[rows], dtype=torch.float32), window(p.valid, torch.bool),
                              window(ka), window(vc), sigma)
        el = torch.tensor([float(p.cells[i][0] == "B") for i in rows])
        y = model.eval()(x, torch.as_tensor(rows, dtype=torch.long), el)
        out.append(((anc[:, None] + sigma * y).numpy(), rows))
    return out


def _compare(p: Prepared, forecasts, origins: list[int]) -> tuple[np.ndarray, np.ndarray, list[tuple]]:
    """Forecast and measured voltage of every (origin, cell, day) with a measured voltage. Also their (cell, origin, day) indexes."""
    predicted, real, where = [], [], []
    for (ahead, rows), t0 in zip(forecasts, origins):
        horizon = min(config.HORIZON_DAYS, len(p.dates) - 1 - t0)
        if horizon < 1 or rows.size == 0:
            continue
        days = slice(t0 + 1, t0 + 1 + horizon)
        actual = p.v.iloc[days, rows].to_numpy(dtype=float).T
        measured = p.obj.iloc[days, rows].to_numpy(dtype=bool).T & np.isfinite(actual)
        c, d = np.nonzero(measured)
        predicted.append(ahead[:, :horizon][c, d])
        real.append(actual[c, d])
        where.append((rows[c], t0 + 1 + d))
    if not predicted:
        raise TrainingDataError("There are no measured voltages after the validation origins to compare the forecasts with")
    return np.concatenate(predicted), np.concatenate(real), where


def _metrics(predicted: np.ndarray, real: np.ndarray) -> dict:
    err = predicted - real
    return {
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "mape": float(100 * np.mean(np.abs(err) / np.abs(real))),
        "r2": float(1 - (err ** 2).sum() / ((real - real.mean()) ** 2).sum()),
    }


def _fit_with_early_stopping(p: Prepared, cfg: dict, log):
    """Trains on every day of `p` but its last ES_BLOCK_DAYS and stops when the error on them stops improving."""
    T, L = len(p.dates), config.LOOKBACK_DAYS
    data = SeriesTensors(p, p.sigma)
    data.set_level_shifts(level_shifts(p.v, p.codes, config.STEP_THRESHOLD_MASK))
    cut = T - config.ES_BLOCK_DAYS
    val_pairs = data.origins(cut, T - 2, stride=7)
    if len(data.origins(L - 1, cut - 1)[1]) == 0 or len(val_pairs[1]) == 0:
        raise TrainingDataError("There are not enough complete in-service windows to train")
    torch.manual_seed(config.SEED)
    model = build_model(len(p.cells), len(FEATURES), cfg)
    return model, fit(model, data, (L - 1, cut - 1), cut - 1, cfg, val_pairs=val_pairs, val_target_limit=T - 1, log=log)


def train(silver: pd.DataFrame, cfg: dict = config.TRAIN, n_jobs: int = -1, log=None) -> TrainingResult:
    """
    The PoC protocol, then the model that serves.
    1. Validation: train on the first (1 - VAL_FRACTION) of the days, stopping early on its last ES_BLOCK_DAYS, and measure
       RMSE, MAE, MAPE and R2 on the rest with forecasts from origins every EVAL_ORIGIN_STRIDE_DAYS days. Those days are
       never trained on nor used to choose anything, and the filtering and scaling see only the training days.
    2. Serving model: train again on every day for as many epochs, and forecast the next HORIZON_DAYS days.
    The reported metrics are the ones of step 1, which has the same recipe as step 2 but less data.
    """
    _limit_threads()
    all_dates = pd.DatetimeIndex(sorted(silver["fecha"].unique()))
    T = len(all_dates)
    if T < config.MIN_DAYS:
        raise TrainingDataError(f"The data covers {T} days; at least {config.MIN_DAYS} are needed to train and validate")
    n_train = T - round(T * config.VAL_FRACTION)

    train_part = prepare(silver[silver["fecha"] <= all_dates[n_train - 1]], n_jobs)
    early, stopped = _fit_with_early_stopping(train_part, cfg, log)

    p = prepare(silver, n_jobs)
    ka, vc, _ = covariates_z(silver, p.cells, p.dates, train_part.covariates)  # as the validation model was trained
    origins = list(range(n_train - 1, T - 1, config.EVAL_ORIGIN_STRIDE_DAYS))
    forecasts = _forecast(early, p, ka, vc, train_part.sigma, origins, n_jobs)
    predicted, real, _ = _compare(p, forecasts, origins)
    metrics = _metrics(predicted, real)

    t_back = T - 1 - config.BACKTEST_DAYS  # inside the validation days, so the model has not seen what comes after
    (back, rows), = _forecast(early, p, ka, vc, train_part.sigma, [t_back], n_jobs)
    b_pred, b_real, ((b_cells, b_days),) = _compare(p, [(back, rows)], [t_back])
    evaluation = pd.DataFrame({
        "celda": np.array(p.cells)[b_cells], "fecha": p.dates[b_days], "predicho": b_pred, "real": b_real,
    })

    data = SeriesTensors(p, p.sigma)
    data.set_level_shifts(level_shifts(p.v, p.codes, config.STEP_THRESHOLD_MASK))
    torch.manual_seed(config.SEED)
    final = build_model(len(p.cells), len(FEATURES), cfg)
    fit(final, data, (config.LOOKBACK_DAYS - 1, T - 2), T - 1, cfg, epochs=stopped["best_epoch"])

    (ahead, rows), = _forecast(final, p, p.ka, p.vc, p.sigma, [T - 1], n_jobs)
    if rows.size == 0:
        raise TrainingDataError("No cell has recent in-service data to forecast from")
    days = p.dates[-1] + pd.to_timedelta(np.arange(1, config.HORIZON_DAYS + 1), unit="D")
    predictions = pd.DataFrame({
        "celda": np.repeat(np.array(p.cells)[rows], config.HORIZON_DAYS),
        "fecha": np.tile(days, rows.size),
        "voltaje": ahead.ravel(),
    })

    scalers = {"sigma_delta": p.sigma, "covariables": p.covariates, "cov_clip": config.COV_CLIP,
               "anchor_days": config.ANCHOR_DAYS, "lookback_days": config.LOOKBACK_DAYS, "horizon_days": config.HORIZON_DAYS,
               "trained_until": str(p.dates[-1].date()), "best_epoch": stopped["best_epoch"],
               "validation": {**metrics, "origins": len(origins), "stride_days": config.EVAL_ORIGIN_STRIDE_DAYS,
                              "from": str(p.dates[n_train].date()), "to": str(p.dates[-1].date())}}
    buffer = BytesIO()
    torch.save({"state_dict": final.state_dict(), "cells": p.cells, "features": FEATURES, "train_cfg": cfg,
                "vmd_params": p.params, **scalers}, buffer)
    return TrainingResult(buffer.getvalue(), scalers, predictions, evaluation, metrics, stopped["best_epoch"])
