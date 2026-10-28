"""Builds small voltage workbooks in memory for the ETL tests."""
from datetime import datetime, timedelta
from io import BytesIO

import openpyxl


def section_rows(days: int = 30, cells: list[int] | None = None, extra_columns: tuple[str, ...] = ()) -> list[list]:
    """Header + one row per day: Date, [Volts], [kA], one column per cell number, then any extra columns."""
    cells = cells or [1, 2, 3]
    rows = [["Date", "[Volts]", "[kA]", *cells, *extra_columns]]
    for day in range(days):
        rows.append([datetime(2026, 1, 1) + timedelta(days=day), 3.0 * len(cells), 12.0,
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
