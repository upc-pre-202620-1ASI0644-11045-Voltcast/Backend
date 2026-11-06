import pandas as pd
import pytest

from tests.excel_files import section_rows, workbook_bytes, xls_bytes
from worker.etl.excel import SchemaError, read_sections, section_of
from worker.etl.pipeline import build_silver, cleaning_counts


def silver_of(sheets: dict[str, list[list]]):
    return build_silver(read_sections(workbook_bytes(sheets)))


class TestSectionOfSheet:
    @pytest.mark.parametrize("name, section", [
        ("EL A 2020_2026", "A"), ("EL_B", "B"), ("Sección A", "A"), ("seccion_c", "C"), ("el-d", "D"),
        ("Resumen", None), ("Hoja1", None), ("EL AB", None), ("Level A", None),
    ])
    def test_the_letter_after_el_or_seccion_names_the_section(self, name, section):
        assert section_of(name) == section


class TestReadSections:  # US002, US003
    def test_identifies_the_sections_and_their_cells(self):
        sections = read_sections(workbook_bytes({
            "EL A 2020_2026": section_rows(cells=[1, 2, 3]), "Sección B": section_rows(cells=[1, 2]),
            "Notas": [["nothing", "to see"]],
        }))
        assert {el: schema.cell_cols for el, (_, schema) in sections.items()} == {"A": ["1", "2", "3"], "B": ["1", "2"]}

    def test_rejects_a_file_without_a_section_sheet(self):
        with pytest.raises(SchemaError, match="No sheet identifies an electrical section"):
            read_sections(workbook_bytes({"Hoja1": section_rows()}))

    def test_rejects_the_same_section_in_two_sheets(self):
        with pytest.raises(SchemaError, match="more than one sheet"):
            read_sections(workbook_bytes({"EL A": section_rows(), "Sección A": section_rows()}))

    def test_rejects_a_sheet_without_a_date_column(self):
        rows = section_rows()
        rows[0][0] = "Fecha"
        with pytest.raises(SchemaError, match="date column"):
            read_sections(workbook_bytes({"EL A": rows}))

    def test_rejects_a_sheet_without_voltage_and_current_columns(self):
        rows = [[row[0], *row[3:]] for row in section_rows()]
        with pytest.raises(SchemaError, match=r"\[Volts\]"):
            read_sections(workbook_bytes({"EL A": rows}))

    def test_says_when_no_electrical_cells_are_found(self):
        rows = [row[:3] for row in section_rows()]
        with pytest.raises(SchemaError, match="No electrical cells were found"):
            read_sections(workbook_bytes({"EL A": rows}))

    def test_rejects_a_cell_numbered_zero(self):
        with pytest.raises(SchemaError, match="numbered from 1"):
            read_sections(workbook_bytes({"EL A": section_rows(cells=[0, 1])}))

    def test_rejects_non_numeric_voltages(self):
        rows = section_rows()
        rows[1][3] = "n/a"
        with pytest.raises(SchemaError, match="non-numeric"):
            read_sections(workbook_bytes({"EL A": rows}))

    def test_rejects_a_file_that_is_not_a_workbook(self):
        with pytest.raises(SchemaError, match="not a valid Excel workbook"):
            read_sections(b"this is not an excel file")


class TestReadXls:
    def test_gives_the_same_result_as_xlsx(self):
        sheets = {"EL A": section_rows(cells=[1, 2, 3]), "Sección B": section_rows(cells=[1, 2]), "Notas": [["x"]]}
        xls, xlsx = read_sections(xls_bytes(sheets), ".xls"), read_sections(workbook_bytes(sheets))
        assert xls.keys() == xlsx.keys() == {"A", "B"}
        for el in xls:
            assert xls[el][1] == xlsx[el][1]
            pd.testing.assert_frame_equal(xls[el][0], xlsx[el][0], check_dtype=False)

    def test_a_corrupt_xls_is_not_a_valid_workbook(self):
        for content in (b"this is not an excel file", xls_bytes({"EL A": section_rows()})[:300]):
            with pytest.raises(SchemaError, match="not a valid Excel workbook"):
                read_sections(content, ".xls")


class TestCleaningCounts:  # US004, TS008
    def test_counts_duplicates_undated_rows_and_extra_columns(self):
        rows = section_rows(days=12, cells=[1], extra_columns=("Average", "Comments"))
        rows.append([rows[4][0], 3.0, 12.0, 3.5, "x", "x"])  # a repeated day
        rows.append([rows[5][0], 3.0, 12.0, 3.5, "x", "x"])  # another one
        rows.append([None, 3.0, 12.0, 3.5, "x", "x"])  # voltage data without a date
        counts = cleaning_counts(read_sections(workbook_bytes({"EL A": rows, "EL B": section_rows(days=12, cells=[1])})))
        assert counts == {"rows_read": 27, "rows_sorted": 24, "duplicates_removed": 2, "discarded_rows": 1, "discarded_columns": 2}

    def test_a_clean_file_discards_nothing(self):
        counts = cleaning_counts(read_sections(workbook_bytes({"EL A": section_rows(days=12)})))
        assert counts == {"rows_read": 12, "rows_sorted": 12, "duplicates_removed": 0, "discarded_rows": 0, "discarded_columns": 0}


class TestBuildSilver:  # US004
    def test_names_cells_by_section_letter_and_header_number(self):
        result = silver_of({"EL A": section_rows(cells=[1, 2, 5]), "EL B": section_rows(cells=[1])})
        assert result.cell_names == ["A1", "A2", "A5", "B1"]
        assert result.summary["sections"] == {"A": 3, "B": 1} and result.summary["n_cells"] == 4
        assert set(result.silver["celda"]) == {"A_c001", "A_c002", "A_c005", "B_c001"}

    def test_keeps_one_record_per_date_and_the_last_one_of_a_duplicate(self):
        rows = section_rows(days=12, cells=[1])
        rows.append([rows[4][0], 3.0, 12.0, 3.5])  # same date as day 4, later in the file
        result = silver_of({"EL A": rows})
        silver = result.silver
        assert len(silver) == 12 and silver["fecha"].is_unique
        assert result.silver.loc[silver["fecha"] == rows[4][0], "voltaje"].item() == 3.5

    def test_orders_the_records_by_date_and_fills_missing_days(self):
        rows = section_rows(days=12, cells=[1])
        del rows[5]  # a day without any record
        rows[1:] = rows[1:][::-1]  # unordered
        silver = silver_of({"EL A": rows}).silver
        assert silver["fecha"].is_monotonic_increasing and len(silver) == 12
        assert silver["fecha"].diff().dropna().eq(pd.Timedelta(days=1)).all()

    def test_drops_the_columns_that_are_not_voltage(self):
        silver = silver_of({"EL A": section_rows(extra_columns=("Average", "Comments"))}).silver
        assert set(silver.columns) == {"fecha", "electrolizador", "celda", "voltaje", "kA", "V_total", "n_en_servicio", "calidad"}

    def test_flags_shutdown_days_and_interpolates_short_gaps(self):
        rows = section_rows(days=20, cells=[1, 2])
        rows[6][2] = 2.0  # day 5: kA below the shutdown threshold
        rows[11][3] = None  # day 10: a one-day gap in cell 1
        silver = silver_of({"EL A": rows}).silver
        cell1 = silver[silver["celda"] == "A_c001"].set_index("fecha")["calidad"].astype(str)
        assert cell1.iloc[5] == "paro" and cell1.iloc[10] == "interpolado" and cell1.iloc[0] == "ok"
        assert silver["voltaje"].loc[silver["calidad"] == "interpolado"].notna().all()

    def test_replaces_an_isolated_outlier_by_an_interpolated_value(self):
        rows = section_rows(days=20, cells=[1, 2])
        rows[8][3] = 9.0  # day 7: above the plausible voltage
        cell1 = silver_of({"EL A": rows}).silver.query("celda == 'A_c001'").reset_index(drop=True)
        assert cell1.loc[7, "calidad"] == "interpolado" and cell1.loc[7, "voltaje"] == pytest.approx(3.001)

    def test_keeps_the_last_fifth_of_the_days_for_validation(self):
        split = silver_of({"EL A": section_rows(days=30)}).split
        assert (split["n_train"], split["n_val"], split["fecha_corte"]) == (24, 6, "2026-01-25")

    def test_rejects_a_file_with_too_few_days(self):
        with pytest.raises(SchemaError, match="at least"):
            silver_of({"EL A": section_rows(days=3)})
