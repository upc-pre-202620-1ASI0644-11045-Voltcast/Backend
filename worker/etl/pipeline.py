from dataclasses import dataclass

import pandas as pd

from worker.etl import config
from worker.etl.cleaning import calendar_from, daily_wide, finalize_long, silver_section, temporal_split
from worker.etl.excel import SchemaError, SheetSchema


@dataclass
class SilverResult:
    silver: pd.DataFrame
    level_shifts: pd.DataFrame
    split: dict
    summary: dict
    cell_names: list[str]  # database names of the cells found: letter + header number (A1, A2, ..., B1, ...)


def build_silver(sections: dict[str, tuple[pd.DataFrame, SheetSchema]]) -> SilverResult:
    """Bronze rows of every section -> clean, ordered and deduplicated daily table (US002-US004)."""
    calendar = calendar_from(*(df for df, _ in sections.values()))
    if len(calendar) < config.MIN_DAYS:
        raise SchemaError(f"The file covers {len(calendar)} days; at least {config.MIN_DAYS} are needed")

    parts, shifts = [], []
    for el in sorted(sections):
        df, schema = sections[el]
        largo, saltos = silver_section(daily_wide(df, el, schema.cell_cols, calendar), el)
        parts.append(largo)
        shifts.append(saltos)
    silver = finalize_long(parts)

    cells = {el: len(sections[el][1].cell_cols) for el in sorted(sections)}
    return SilverResult(
        silver=silver,
        level_shifts=pd.concat(shifts, ignore_index=True).sort_values(["electrolizador", "celda", "fecha"], ignore_index=True),
        split=temporal_split(calendar),
        summary={
            "sections": cells,
            "n_cells": sum(cells.values()),
            "date_from": str(calendar[0].date()),
            "date_to": str(calendar[-1].date()),
            "days": len(calendar),
        },
        cell_names=[f"{el}{int(c)}" for el in sorted(sections) for c in sections[el][1].cell_cols],
    )


def raw_row_count(sections: dict[str, tuple[pd.DataFrame, SheetSchema]]) -> int:
    return sum(len(df) for df, _ in sections.values())
