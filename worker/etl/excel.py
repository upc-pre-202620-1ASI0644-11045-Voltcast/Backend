"""Reads the uploaded workbook (.xlsx, .xlsm, .xls): finds the electrical sections, the columns and the cells (US001-US003)."""
import re
import struct
from dataclasses import dataclass
from io import BytesIO
from zipfile import BadZipFile

import openpyxl
import pandas as pd
import xlrd
from openpyxl.utils.exceptions import InvalidFileException

DATE_COL = "Date"
VOLTS_COL = "[Volts]"
KA_COL = "[kA]"

# "EL A", "EL_A 2020_2026", "Sección A", "Seccion_B": the letter after EL / Sección names the section.
SECTION_PATTERN = re.compile(r"\b(?:el|secci[oó]n)[\s_\-]*([a-z])(?![a-z])", re.IGNORECASE)


class SchemaError(ValueError):
    """The file does not have the expected structure; the message is shown to the user (US001-US003)."""


@dataclass
class SheetSchema:
    cell_cols: list[str]  # header numbers of the cell columns, as text ("1", "2", ...)
    discarded_columns: int = 0  # columns that are not date, voltage, current or cell
    rows_without_date: int = 0  # records dropped because their date is empty


def section_of(sheet_name: str) -> str | None:
    match = SECTION_PATTERN.search(sheet_name)
    return match.group(1).upper() if match else None


def _header_to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _frame(title: str, rows) -> pd.DataFrame:
    """Header + data rows (tuples of cell values) -> DataFrame; the same for every format."""
    rows = iter(rows)
    header = next(rows, None)
    if header is None:
        raise SchemaError(f"Sheet '{title}' is empty")
    data = [r for r in rows if any(v is not None for v in r)]
    df = pd.DataFrame(data, columns=[_header_to_text(h) for h in header])
    for c in df.columns[df.isna().all()]:  # a column without any value (a cell out of service the whole period) is not text: it is a gap
        df[c] = df[c].astype(float)
    # Columns without a header and completely empty are the borders of the sheet.
    return df.drop(columns=[c for c in df.columns if c == "" and df[c].isna().all()])


def detect_schema(df: pd.DataFrame, sheet: str) -> SheetSchema:
    """Identifies the date, [Volts], [kA] and cell columns of a sheet; raises SchemaError saying what is missing."""
    cols = list(df.columns)
    if DATE_COL not in cols:
        raise SchemaError(f"Could not identify the date column '{DATE_COL}' in sheet '{sheet}'. Check the structure of the file")
    missing = [c for c in (VOLTS_COL, KA_COL) if c not in cols]
    if missing:
        raise SchemaError(f"Could not identify the columns {missing} in sheet '{sheet}' (total voltage / current). Check the structure of the file")
    cell_cols = [c for c in cols if c.isdigit()]
    if not cell_cols:
        raise SchemaError(f"No electrical cells were found in sheet '{sheet}': cell columns are named with their number (1, 2, 3...)")
    if len(set(cols)) != len(cols):
        raise SchemaError(f"Sheet '{sheet}' has repeated column headers")
    if any(int(c) < 1 for c in cell_cols):
        raise SchemaError(f"Sheet '{sheet}' has a cell column numbered 0; cells are numbered from 1")
    non_numeric = [c for c in cell_cols + [VOLTS_COL, KA_COL] if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        raise SchemaError(f"Sheet '{sheet}' has voltage or current columns with non-numeric values: {non_numeric[:10]}")
    if not pd.api.types.is_datetime64_any_dtype(df[DATE_COL]):
        raise SchemaError(f"The column '{DATE_COL}' of sheet '{sheet}' does not contain dates")
    return SheetSchema(cell_cols, discarded_columns=len(cols) - 3 - len(cell_cols))


def _finish(frames) -> dict[str, tuple[pd.DataFrame, SheetSchema]]:
    """(section, sheet name, rows) -> section -> (dated rows, schema); the checks are the same for every format."""
    sections: dict[str, tuple[pd.DataFrame, SheetSchema]] = {}
    for section, name, df in frames:
        if section in sections:
            raise SchemaError(f"Section {section} appears in more than one sheet")
        schema = detect_schema(df, name)
        dated = df.dropna(subset=[DATE_COL])
        schema.rows_without_date = len(df) - len(dated)
        sections[section] = (dated, schema)
    return sections


def _workbook_sections(names: list[str], rows_of) -> dict[str, tuple[pd.DataFrame, SheetSchema]]:
    """Every sheet whose name identifies a section; other sheets are ignored."""
    frames = ((section_of(n), n, _frame(n, rows_of(n))) for n in names if section_of(n) is not None)
    sections = _finish(frames)
    if not sections:
        raise SchemaError(f"No sheet identifies an electrical section (for example 'EL A' or 'Sección A'). Sheets found: {names}")
    return sections


def _xls_rows(sheet):
    for r in range(sheet.nrows):
        row = []
        for cell in sheet.row(r):
            if cell.ctype == xlrd.XL_CELL_DATE:
                row.append(xlrd.xldate.xldate_as_datetime(cell.value, sheet.book.datemode))
            elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR) or cell.value == "":
                row.append(None)
            else:
                row.append(cell.value)
        yield tuple(row)


def _read_xls(content: bytes):
    try:
        book = xlrd.open_workbook(file_contents=content)
        # Corrupt files can fail while a sheet is read, so read them all inside the try.
        rows = {n: list(_xls_rows(book.sheet_by_name(n))) for n in book.sheet_names()}
    except (xlrd.XLRDError, struct.error, IndexError, KeyError, AssertionError, ValueError, OSError) as error:
        raise SchemaError("The file is not a valid Excel workbook") from error
    return _workbook_sections(list(rows), rows.__getitem__)


def read_sections(content: bytes, extension: str = ".xlsx") -> dict[str, tuple[pd.DataFrame, SheetSchema]]:
    """Section letter -> (rows, schema), one sheet per section."""
    if extension.lower() == ".xls":
        return _read_xls(content)
    try:
        workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError) as error:
        raise SchemaError("The file is not a valid Excel workbook") from error
    try:
        return _workbook_sections(workbook.sheetnames, lambda n: workbook[n].iter_rows(values_only=True))
    finally:
        workbook.close()
