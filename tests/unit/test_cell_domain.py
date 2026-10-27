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
    @pytest.mark.parametrize(
        "assigned, active",
        [(set(), False), ({0}, False), ({1}, False), ({0, 1}, True)],
    )
    def test_active_only_with_a_cathode_and_an_anode(self, assigned, active):
        cell = Cell(id=1, name="A1", is_active=not active)
        cell.refresh_status(assigned)
        assert cell.is_active is active

    def test_hide_and_show(self):
        cell = Cell(id=1, name="A1", is_active=False, is_visible=True)
        cell.hide()
        assert not cell.is_visible
        cell.show()
        assert cell.is_visible

    def test_barcode_is_derived_from_the_id_and_kept_once_generated(self):
        cell = Cell(id=7, name="A1", is_active=True)
        cell.generate_barcode()
        assert cell.barcode_value == "CELL-00007"
        cell.barcode_value = "CELL-CUSTOM"
        cell.generate_barcode()
        assert cell.barcode_value == "CELL-CUSTOM"

    def test_no_barcode_for_an_inactive_cell(self):
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

    def test_reactivate_frees_a_disabled_component(self):
        component = Component(id=1, type=0, serial_code="C-1", is_active=False, is_visible=False, cell_id=None)
        component.reactivate()
        assert (component.is_active, component.is_visible, component.cell_id) == (True, True, None)
        with pytest.raises(ValueError, match="already active"):
            component.reactivate()

    def test_only_a_disabled_component_can_be_hidden(self):
        component = Component(id=1, type=0, serial_code="C-1", is_active=True, is_visible=True)
        with pytest.raises(ValueError, match="disabled"):
            component.hide()
        component.disable()
        component.hide()
        assert not component.is_visible

    def test_revive_brings_back_a_component_with_its_new_type_and_cell(self):
        component = Component(id=1, type=0, serial_code="C-1", is_active=False, is_visible=False)
        component.revive(ComponentType.ANODE, 4)
        assert (component.type, component.is_active, component.is_visible, component.cell_id) == (1, True, True, 4)

    def test_update_info(self):
        component = Component(id=1, type=0, serial_code="C-1", is_active=True)
        component.update_info(serial_code="C-2", component_type=ComponentType.ANODE)
        assert (component.serial_code, component.type) == ("C-2", 1)
