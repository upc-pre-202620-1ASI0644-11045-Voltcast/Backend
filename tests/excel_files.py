"""Builds small voltage workbooks in memory for the ETL tests."""
from datetime import datetime, timedelta
from io import BytesIO

import openpyxl


def section_rows(days: int = 30, cells: list[int] | None = None, extra_columns: tuple[str, ...] = (),
                 start: datetime = datetime(2026, 1, 1)) -> list[list]:
    """Header + one row per day: Date, [Volts], [kA], one column per cell number, then any extra columns."""
    cells = cells or [1, 2, 3]
    rows = [["Date", "[Volts]", "[kA]", *cells, *extra_columns]]
    for day in range(days):
        rows.append([start + timedelta(days=day), 3.0 * len(cells), 12.0,
                     *(3.0 + 0.001 * n for n in cells), *("x" for _ in extra_columns)])
    return rows


def workbook_bytes(sheets: dict[str, list[list]]) -> bytes:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def varying_rows(days: int = 520, cells: list[int] | None = None, seed: int = 0) -> list[list]:
    """Like section_rows but with a slow trend and noise, so a model has something to learn."""
    import numpy as np

    cells = cells or [1, 2, 3, 4]
    rng = np.random.default_rng(seed)
    t = np.arange(days)
    level = 3.2 + 0.05 * np.sin(t / 60) + 0.00005 * t
    ka = 14.8 + rng.normal(0, 0.3, days)
    rows = [["Date", "[Volts]", "[kA]", *cells]]
    for day in range(days):
        volts = [float(level[day] + 0.01 * n + rng.normal(0, 0.004)) for n in cells]
        rows.append([datetime(2020, 1, 1) + timedelta(days=day), sum(volts), float(ka[day]), *volts])
    return rows
