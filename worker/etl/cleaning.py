"""
Silver layer rules ported from the PoC (src/voltcast/cleaning.py, R1-R9), so the model trains on the same data.
The quality codes keep the PoC names because the training stage reads them.
"""
import numpy as np
import pandas as pd

from worker.etl import config
from worker.etl.excel import DATE_COL, KA_COL, VOLTS_COL

# Quality codes, from lowest to highest precedence when assigned
CALIDAD = ["ok", "interpolado", "hueco", "atipico", "paro", "fuera_servicio"]


def cell_name(el: str, n: int | str) -> str:
    return f"{el}_c{int(n):03d}"


def daily_wide(bronze: pd.DataFrame, el: str, cell_cols: list[str], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Rows of a section -> continuous daily table with `{el}_V_total`, `{el}_kA`, `{el}_c001`...
    Any column that is not date, voltage or current is dropped. With repeated dates the last record of the day wins.
    """
    df = bronze.sort_values(DATE_COL, kind="stable")
    df = df.assign(fecha=df[DATE_COL].dt.normalize()).drop_duplicates("fecha", keep="last").set_index("fecha")
    rename = {VOLTS_COL: f"{el}_V_total", KA_COL: f"{el}_kA", **{c: cell_name(el, c) for c in cell_cols}}
    out = df[list(rename)].rename(columns=rename).reindex(calendar)
    out.index.name = "fecha"
    return out


def calendar_from(*bronzes: pd.DataFrame) -> pd.DatetimeIndex:
    fechas = pd.concat([b[DATE_COL].dt.normalize() for b in bronzes])
    return pd.date_range(fechas.min(), fechas.max(), freq="D", name="fecha")


def true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Consecutive True stretches as inclusive (start, end) pairs."""
    m = np.concatenate([[False], np.asarray(mask, dtype=bool), [False]])
    d = np.diff(m.astype(np.int8))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0] - 1))


def interpolate_short_gaps(s: pd.Series, max_days: int, blocked: np.ndarray | None = None) -> tuple[pd.Series, np.ndarray]:
    """
    Linearly interpolates the inner gaps of up to `max_days` days. Longer gaps, gaps at the ends and gaps touching a
    `blocked` day stay NaN. Returns the series and the mask of interpolated values.
    """
    vals = s.to_numpy(dtype=float, copy=True)
    filled = np.zeros(len(vals), dtype=bool)
    for a, b in true_runs(np.isnan(vals)):
        if a == 0 or b == len(vals) - 1 or b - a + 1 > max_days:
            continue
        if blocked is not None and blocked[a:b + 1].any():
            continue
        vals[a:b + 1] = np.interp(np.arange(a, b + 1), [a - 1, b + 1], [vals[a - 1], vals[b + 1]])
        filled[a:b + 1] = True
    return pd.Series(vals, index=s.index, name=s.name), filled


def out_of_service_mask(v: pd.DataFrame, ka: pd.Series,
                        min_days: int = config.OOS_MIN_DAYS, merge_days: int = config.OOS_MERGE_DAYS) -> pd.DataFrame:
    """
    Out-of-service stretches per cell. An informative day has normal kA and data in most cells; on those days a cell is
    "bad" if V < V_OUT_OF_SERVICE (negatives included) or its data is missing. Bad stretches separated by up to
    `merge_days` good informative days are joined, and kept if they span at least `min_days` calendar days.
    """
    informativo = (ka >= config.KA_SHUTDOWN) & (v.notna().sum(axis=1) > v.shape[1] // 2)
    pos = np.where(informativo.to_numpy())[0]
    malo = ((v < config.V_OUT_OF_SERVICE) | v.isna()).to_numpy()[pos]
    out = np.zeros(v.shape, dtype=bool)
    for j in range(v.shape[1]):
        merged: list[list[int]] = []
        for a, b in true_runs(malo[:, j]):
            if merged and a - merged[-1][1] - 1 <= merge_days:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        for a, b in merged:
            ini, fin = pos[a], pos[b]
            if (v.index[fin] - v.index[ini]).days + 1 >= min_days:
                out[ini:fin + 1, j] = True
    return pd.DataFrame(out, index=v.index, columns=v.columns)


def quality(v: pd.DataFrame, ka: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    (clean voltage, quality code) of the cells of a section.
    fuera_servicio: out-of-service stretches -> NaN. paro: kA < KA_SHUTDOWN -> NaN. atipico: isolated V > V_MAX_PLAUSIBLE
    or V < V_OUT_OF_SERVICE -> NaN. hueco: no data. Gaps and outliers of up to MAX_INTERP_DAYS become `interpolado`.
    """
    oos = out_of_service_mask(v, ka)
    paro = np.broadcast_to((ka < config.KA_SHUTDOWN).to_numpy()[:, None], v.shape)
    raw = v.to_numpy()
    atip = ((raw > config.V_MAX_PLAUSIBLE) | (raw < config.V_OUT_OF_SERVICE)) & ~paro
    code = np.zeros(v.shape, dtype=np.int8)  # ok
    code[np.isnan(raw)] = CALIDAD.index("hueco")
    code[atip] = CALIDAD.index("atipico")
    code[paro] = CALIDAD.index("paro")
    code[oos.to_numpy()] = CALIDAD.index("fuera_servicio")

    clean = v.where(code == 0)
    blocked = code == CALIDAD.index("fuera_servicio")
    for j, c in enumerate(v.columns):
        clean[c], filled = interpolate_short_gaps(clean[c], config.MAX_INTERP_DAYS, blocked[:, j])
        reclasificar = filled & np.isin(code[:, j], [CALIDAD.index("hueco"), CALIDAD.index("atipico")])
        code[reclasificar, j] = CALIDAD.index("interpolado")
    return clean, pd.DataFrame(code, index=v.index, columns=v.columns)


def level_shifts(clean: pd.DataFrame, code: pd.DataFrame,
                 threshold: float = config.STEP_THRESHOLD_V, window: int = config.STEP_WINDOW_DAYS) -> pd.DataFrame:
    """
    Level shifts per cell: |median(next 7 days) - median(previous 7 days)| > threshold, on ok/interpolado days only.
    `fecha` is the first day of the new level. For diagnosis only: the model does not read it.
    """
    valid = clean.where(code.isin([CALIDAD.index(c) for c in ("ok", "interpolado")]))
    min_p = max(1, window // 2 + 1)
    antes = valid.rolling(window, min_periods=min_p).median()
    despues = valid[::-1].rolling(window, min_periods=min_p).median()[::-1].shift(-1)
    delta = (despues - antes).to_numpy()
    eventos = []
    for j, c in enumerate(clean.columns):
        d = delta[:, j]
        for a, b in true_runs(np.abs(np.nan_to_num(d)) > threshold):
            k = a + int(np.nanargmax(np.abs(d[a:b + 1])))
            if k + 1 < len(clean):
                eventos.append({"fecha": clean.index[k + 1], "celda": c, "delta_V": float(d[k])})
    return pd.DataFrame(eventos, columns=["fecha", "celda", "delta_V"])


def silver_section(wide: pd.DataFrame, el: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Applies the quality rules to the daily table of a section. Returns (long format, level shifts)."""
    cells = [c for c in wide.columns if c.startswith(f"{el}_c")]
    ka_raw = wide[f"{el}_kA"]
    clean, code = quality(wide[cells], ka_raw)
    ka, _ = interpolate_short_gaps(ka_raw, config.MAX_INTERP_DAYS)
    vtot, _ = interpolate_short_gaps(wide[f"{el}_V_total"], config.MAX_INTERP_DAYS)
    n_srv = (code != CALIDAD.index("fuera_servicio")).sum(axis=1)

    largo = pd.DataFrame({
        "fecha": np.repeat(wide.index.to_numpy(), len(cells)),
        "electrolizador": el,
        "celda": np.tile(cells, len(wide)),
        "voltaje": clean.to_numpy().ravel(),
        "kA": np.repeat(ka.to_numpy(), len(cells)),
        "V_total": np.repeat(vtot.to_numpy(), len(cells)),
        "n_en_servicio": np.repeat(n_srv.to_numpy(), len(cells)).astype(np.int16),
        "calidad": pd.Categorical.from_codes(code.to_numpy().ravel(), categories=CALIDAD),
    })
    saltos = level_shifts(clean, code).assign(electrolizador=el)
    return largo, saltos[["fecha", "electrolizador", "celda", "delta_V"]]


def finalize_long(parts: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(parts, ignore_index=True)
    df["electrolizador"] = df["electrolizador"].astype("category")
    df["celda"] = df["celda"].astype("category")
    df["calidad"] = pd.Categorical(df["calidad"], categories=CALIDAD)
    return df.sort_values(["electrolizador", "celda", "fecha"], ignore_index=True)


def temporal_split(calendar: pd.DatetimeIndex, val_fraction: float = config.VAL_FRACTION) -> dict:
    n = len(calendar)
    n_val = round(n * val_fraction)
    train, val = calendar[: n - n_val], calendar[n - n_val:]
    return {
        "val_fraction": val_fraction,
        "n_dias": n,
        "n_train": len(train),
        "n_val": n_val,
        "train_desde": str(train[0].date()),
        "train_hasta": str(train[-1].date()),
        "val_desde": str(val[0].date()),
        "val_hasta": str(val[-1].date()),
        "fecha_corte": str(val[0].date()),  # first validation day
    }
