"""Reads the uploaded workbook: finds the electrical sections, the columns and the cells (US001-US003)."""
import re
from dataclasses import dataclass
from io import BytesIO
from zipfile import BadZipFile

import openpyxl
import pandas as pd
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


def _read_sheet(worksheet) -> pd.DataFrame:
    rows = worksheet.iter_rows(values_only=True)
    header = next(rows, None)
    if header is None:
        raise SchemaError(f"Sheet '{worksheet.title}' is empty")
    data = [r for r in rows if any(v is not None for v in r)]
    df = pd.DataFrame(data, columns=[_header_to_text(h) for h in header])
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


def read_sections(content: bytes) -> dict[str, tuple[pd.DataFrame, SheetSchema]]:
    """Section letter -> (rows, schema) for every sheet whose name identifies a section. Other sheets are ignored."""
    try:
        workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError) as error:
        raise SchemaError("The file is not a valid Excel workbook") from error
    sections: dict[str, tuple[pd.DataFrame, SheetSchema]] = {}
    try:
        for name in workbook.sheetnames:
            section = section_of(name)
            if section is None:
                continue
            if section in sections:
                raise SchemaError(f"Section {section} appears in more than one sheet")
            df = _read_sheet(workbook[name])
            schema = detect_schema(df, name)
            dated = df.dropna(subset=[DATE_COL])
            schema.rows_without_date = len(df) - len(dated)
            sections[section] = (dated, schema)
        if not sections:
            raise SchemaError(
                f"No sheet identifies an electrical section (for example 'EL A' or 'Sección A'). Sheets found: {workbook.sheetnames}"
            )
    finally:
        workbook.close()
    return sections
