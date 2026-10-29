from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pandas as pd
import torch
from joblib import Parallel, delayed

from worker.etl.cleaning import level_shifts
from worker.training import config, vmd
from worker.training.dataset import FEATURES, SeriesTensors, build_inputs
from worker.training.gold import Prepared, TrainingDataError, prepare
from worker.training.model import build_model, fit


@dataclass
class TrainingResult:
    checkpoint: bytes  # weights and everything needed to rebuild and read the model
    scalers: dict
    predictions: pd.DataFrame  # celda, fecha, voltaje: the next HORIZON_DAYS days after the last day of the data
    evaluation: pd.DataFrame  # celda, fecha, predicho, real: a backtest forecast against the measured voltage
    metrics: dict  # rmse, mae, mape (percentage), r2 over the evaluation rows
    best_epoch: int


def _causal_windows(p: Prepared, t0: int, n_jobs: int) -> np.ndarray:
    """Filtered signal `[C, L]` of the last days up to `t0`, using only data until `t0`."""
    rows = Parallel(n_jobs=n_jobs)(
        delayed(vmd.causal_window)(p.v[c].to_numpy(), p.oos[c].to_numpy(), t0, *p.params[c]) for c in p.cells
    )
    return np.stack(rows)


@torch.no_grad()
def _forecast(model, p: Prepared, t0: int, sigma: float, n_jobs: int) -> tuple[np.ndarray, np.ndarray]:
    """Voltage forecast `[N, H]` from the origin `t0` for the cells whose window is complete, and their indexes."""
    L = config.LOOKBACK_DAYS
    vf_win = _causal_windows(p, t0, n_jobs)
    rows = np.where(np.isfinite(vf_win).all(axis=1))[0]
    if rows.size == 0:
        return np.empty((0, config.HORIZON_DAYS)), rows
    sl = slice(t0 - L + 1, t0 + 1)

    def window(frame: pd.DataFrame, dtype=torch.float32):
        return torch.as_tensor(frame.iloc[sl, rows].to_numpy(dtype=float, copy=True).T, dtype=dtype)

    x, anc = build_inputs(torch.as_tensor(vf_win[rows], dtype=torch.float32), window(p.valid, torch.bool),
                          window(p.ka), window(p.vc), sigma)
    cell = torch.as_tensor(rows, dtype=torch.long)
    el = torch.tensor([float(p.cells[i][0] == "B") for i in rows])
    y = model.eval()(x, cell, el)
    return (anc[:, None] + sigma * y).numpy(), rows


def _metrics(predicted: np.ndarray, real: np.ndarray) -> dict:
    err = predicted - real
    return {
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "mape": float(100 * np.mean(np.abs(err) / np.abs(real))),
        "r2": float(1 - (err ** 2).sum() / ((real - real.mean()) ** 2).sum()),
    }


def train(silver: pd.DataFrame, cfg: dict = config.TRAIN, n_jobs: int = -1, log=None) -> TrainingResult:
    """
    Trains the Bi-LSTM on every day of the Silver table, forecasts the next HORIZON_DAYS days of each cell and
    evaluates the model with a backtest, like the PoC (notebook 06): the last ES_BLOCK_DAYS days stop the training
    early and are never trained on; the model is then trained again on all the days for as many epochs.
    The backtest forecasts BACKTEST_DAYS days from an origin inside that block with the model that did not train on it.
    """
    p = prepare(silver, n_jobs)
    T, L = len(p.dates), config.LOOKBACK_DAYS
    if T < config.MIN_DAYS:
        raise TrainingDataError(f"The data covers {T} days; at least {config.MIN_DAYS} are needed to train and evaluate")

    data = SeriesTensors(p, p.sigma)
    data.set_level_shifts(level_shifts(p.v, p.codes, config.STEP_THRESHOLD_MASK))
    cut = T - config.ES_BLOCK_DAYS
    val_pairs = data.origins(cut, T - 2, stride=7)
    if len(data.origins(L - 1, cut - 1)[1]) == 0 or len(val_pairs[1]) == 0:
        raise TrainingDataError("There are not enough complete in-service windows to train and evaluate")

    torch.manual_seed(config.SEED)
    early = build_model(len(p.cells), len(FEATURES), cfg)
    stopped = fit(early, data, (L - 1, cut - 1), cut - 1, cfg, val_pairs=val_pairs, val_target_limit=T - 1, log=log)
    torch.manual_seed(config.SEED)
    final = build_model(len(p.cells), len(FEATURES), cfg)
    fit(final, data, (L - 1, T - 2), T - 1, cfg, epochs=stopped["best_epoch"])

    t_eval = T - 1 - config.BACKTEST_DAYS
    back, rows = _forecast(early, p, t_eval, p.sigma, n_jobs)
    horizon = slice(t_eval + 1, t_eval + 1 + config.BACKTEST_DAYS)
    real = p.v.iloc[horizon, rows].to_numpy(dtype=float).T
    measured = p.obj.iloc[horizon, rows].to_numpy(dtype=bool).T & np.isfinite(real)
    cell_idx, day_idx = np.nonzero(measured)
    if cell_idx.size == 0:
        raise TrainingDataError("There are no measured voltages after the evaluation origin to compare the forecast with")
    predicted = back[:, :config.BACKTEST_DAYS][cell_idx, day_idx]
    evaluation = pd.DataFrame({
        "celda": np.array(p.cells)[rows][cell_idx],
        "fecha": p.dates[t_eval + 1 + day_idx],
        "predicho": predicted,
        "real": real[cell_idx, day_idx],
    })

    ahead, rows = _forecast(final, p, T - 1, p.sigma, n_jobs)
    if rows.size == 0:
        raise TrainingDataError("No cell has recent in-service data to forecast from")
    days = p.dates[-1] + pd.to_timedelta(np.arange(1, config.HORIZON_DAYS + 1), unit="D")
    predictions = pd.DataFrame({
        "celda": np.repeat(np.array(p.cells)[rows], config.HORIZON_DAYS),
        "fecha": np.tile(days, rows.size),
        "voltaje": ahead.ravel(),
    })

    scalers = {"sigma_delta": p.sigma, "covariables": p.covariates, "cov_clip": config.COV_CLIP,
               "anchor_days": config.ANCHOR_DAYS, "lookback_days": L, "horizon_days": config.HORIZON_DAYS,
               "trained_until": str(p.dates[-1].date()), "best_epoch": stopped["best_epoch"]}
    buffer = BytesIO()
    torch.save({"state_dict": final.state_dict(), "cells": p.cells, "features": FEATURES, "train_cfg": cfg,
                "vmd_params": p.params, **scalers}, buffer)
    return TrainingResult(buffer.getvalue(), scalers, predictions, evaluation, _metrics(evaluation["predicho"].to_numpy(),
                                                                                         evaluation["real"].to_numpy()),
                          stopped["best_epoch"])
