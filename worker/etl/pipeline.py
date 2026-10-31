from dataclasses import dataclass
from datetime import date, datetime, timezone

import pandas as pd

from worker.etl import config
from worker.etl.cleaning import calendar_from, daily_wide, finalize_long, silver_section, temporal_split
from worker.etl.excel import DATE_COL, SchemaError, SheetSchema


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


Sections = dict[str, tuple[pd.DataFrame, SheetSchema]]


def date_range(sections: Sections) -> tuple[date, date]:
    dates = pd.concat([df[DATE_COL].dt.normalize() for df, _ in sections.values()])
    return dates.min().date(), dates.max().date()


def check_not_future(sections: Sections) -> None:
    """Records dated after today cannot be measurements: they are forecasts or made up."""
    last = date_range(sections)[1]
    today = datetime.now(timezone.utc).date()
    if last > today:
        raise SchemaError(f"The file has dates after today ({last}); only measured voltages can be uploaded")


def merge_sections(files: list[Sections]) -> Sections:
    """The raw rows of the files, oldest first, as one file: where two have the same day the later one wins (see daily_wide)."""
    merged = files[0]
    for sections in files[1:]:
        if set(sections) != set(merged):
            raise SchemaError(f"The sections of the file ({sorted(sections)}) differ from the ones it complements ({sorted(merged)})")
        for el, (df, schema) in sections.items():
            if schema.cell_cols != merged[el][1].cell_cols:
                raise SchemaError(f"The cells of section {el} differ from the ones of the file it complements")
        merged = {el: (pd.concat([merged[el][0], df], ignore_index=True), schema) for el, (df, schema) in sections.items()}
    return merged


def merge_preview(base: tuple[date, date], new: tuple[date, date]) -> dict:
    """What merging a file that covers `new` into a dataset that covers `base` would do; raises SchemaError if it cannot be merged."""
    gap = (new[0] - base[1]).days - 1
    if new[1] <= base[1]:
        raise SchemaError(f"The file adds no days after {base[1]}, the last day of the dataset it complements")
    if gap > config.MAX_INTERP_DAYS:
        raise SchemaError(f"There are {gap} days without records between {base[1]} and {new[0]}; at most {config.MAX_INTERP_DAYS} can be bridged")
    days = (new[1] - min(base[0], new[0])).days + 1
    if days < config.MIN_DAYS:
        raise SchemaError(f"Merged, the files cover {days} days; at least {config.MIN_DAYS} are needed")
    return {
        "base": {"date_from": str(base[0]), "date_to": str(base[1])},
        "new": {"date_from": str(new[0]), "date_to": str(new[1])},
        "gap_days": max(gap, 0),
        "overlap_days": max((base[1] - new[0]).days + 1, 0),
        "merged_days": days,
    }
