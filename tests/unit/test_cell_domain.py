import pytest

from cell_management.domain.model.aggregates.Cell import Cell
from cell_management.domain.model.aggregates.Component import Component, ComponentType


class TestCellName:
    @pytest.mark.parametrize(
        "raw, expected",
        [("A1", "A1"), ("a2", "A2"), ("  b15 ", "B15"), ("A150", "A150"), ("Z9", "Z9")],
    )
    def test_valid_names_are_normalized_to_uppercase(self, raw, expected):
        assert Cell.normalize_name(raw) == expected

    @pytest.mark.parametrize("raw", ["", "A", "1", "1A", "AI", "A0", "A01", "AA1", "A-1", "A 1", "Celda A1"])
    def test_invalid_names_are_rejected(self, raw):
        with pytest.raises(ValueError, match="letter followed by a number"):
            Cell.normalize_name(raw)


class TestCell:
    def test_disable_twice_is_rejected(self):
        cell = Cell(id=1, name="A1", is_active=True)
        cell.disable()
        assert not cell.is_active
        with pytest.raises(ValueError):
            cell.disable()

    def test_barcode_is_derived_from_the_id_and_kept_once_generated(self):
        cell = Cell(id=7, name="A1", is_active=True)
        cell.generate_barcode()
        assert cell.barcode_value == "CELL-00007"
        cell.barcode_value = "CELL-CUSTOM"
        cell.generate_barcode()
        assert cell.barcode_value == "CELL-CUSTOM"

    def test_no_barcode_for_a_disabled_cell(self):
        with pytest.raises(ValueError):
            Cell(id=1, name="A1", is_active=False).generate_barcode()


class TestComponent:
    def test_component_types_match_the_database_codes(self):
        assert int(ComponentType.CATHODE) == 0 and int(ComponentType.ANODE) == 1

    def test_a_component_in_use_cannot_be_disabled(self):
        component = Component(id=1, type=0, serial_code="C-1", is_active=True, cell_id=3)
        with pytest.raises(ValueError, match="in use"):
            component.disable()
        component.unassign()
        component.disable()
        assert not component.is_active

    def test_a_disabled_component_cannot_be_assigned(self):
        component = Component(id=1, type=0, serial_code="C-1", is_active=False, cell_id=None)
        with pytest.raises(ValueError):
            component.assign_to(2)

    def test_update_info(self):
        component = Component(id=1, type=0, serial_code="C-1", is_active=True)
        component.update_info(serial_code="C-2", component_type=ComponentType.ANODE)
        assert (component.serial_code, component.type) == ("C-2", 1)
