from tests.conftest import API

CELLS = f"{API}/cells"
COMPONENTS = f"{API}/components"


def create_cell(client, headers, name="A1"):
    response = client.post(CELLS, headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_component(client, headers, type_="CATHODE", serial="CAT-1", cell_id=None):
    response = client.post(COMPONENTS, headers=headers, json={"type": type_, "serial_code": serial, "cell_id": cell_id})
    assert response.status_code == 201, response.text
    return response.json()


def equip(client, headers, cell_id, suffix="1"):
    """Assigns a cathode and an anode to the cell."""
    create_component(client, headers, "CATHODE", f"CAT-{suffix}", cell_id)
    create_component(client, headers, "ANODE", f"ANO-{suffix}", cell_id)


class TestRegisterCell:  # US009
    def test_registers_an_inactive_cell_without_barcode(self, client, engineer_headers):
        # Inactive until it gets a cathode and an anode.
        response = client.post(CELLS, headers=engineer_headers, json={"name": "A1"})
        assert response.status_code == 201
        body = response.json()
        assert (body["name"], body["is_active"], body["barcode_value"]) == ("A1", False, None)

    def test_names_are_normalized_to_uppercase(self, client, engineer_headers):
        assert create_cell(client, engineer_headers, " b12 ")["name"] == "B12"

    def test_rejects_names_that_do_not_follow_the_letter_number_format(self, client, engineer_headers):
        for name in ("Celda A1", "AA1", "A", "A0", "1A"):
            response = client.post(CELLS, headers=engineer_headers, json={"name": name})
            assert response.status_code == 400, name
            assert "letter followed by a number" in response.json()["detail"]

    def test_rejects_a_missing_name(self, client, engineer_headers):
        assert client.post(CELLS, headers=engineer_headers, json={}).status_code == 422

    def test_names_are_unique_ignoring_case(self, client, engineer_headers):
        create_cell(client, engineer_headers, "A1")
        response = client.post(CELLS, headers=engineer_headers, json={"name": "a1"})
        assert response.status_code == 400 and "already exists" in response.json()["detail"]

    def test_requires_authentication(self, client):
        assert client.post(CELLS, json={"name": "A1"}).status_code in (401, 403)


class TestReadCells:
    def test_lists_and_filters_by_active_status(self, client, engineer_headers):
        equipped = create_cell(client, engineer_headers, "A1")
        equip(client, engineer_headers, equipped["id"])
        create_cell(client, engineer_headers, "A2")

        everything = client.get(CELLS, headers=engineer_headers).json()
        active = client.get(f"{CELLS}?is_active=true", headers=engineer_headers).json()
        inactive = client.get(f"{CELLS}?is_active=false", headers=engineer_headers).json()
        assert len(everything) == 2
        assert [c["name"] for c in active] == ["A1"]
        assert [c["name"] for c in inactive] == ["A2"]

    def test_get_by_id(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        assert client.get(f"{CELLS}/{cell['id']}", headers=engineer_headers).json()["name"] == "A1"
        assert client.get(f"{CELLS}/999", headers=engineer_headers).status_code == 404


class TestEditCell:  # US010
    def test_updates_the_name(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers, "A1")
        response = client.put(f"{CELLS}/{cell['id']}", headers=engineer_headers, json={"name": "c7"})
        assert response.status_code == 200 and response.json()["name"] == "C7"

    def test_keeping_the_same_name_is_allowed(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers, "A1")
        assert client.put(f"{CELLS}/{cell['id']}", headers=engineer_headers, json={"name": "A1"}).status_code == 200

    def test_rejects_an_invalid_or_taken_name(self, client, engineer_headers):
        first = create_cell(client, engineer_headers, "A1")
        create_cell(client, engineer_headers, "A2")
        assert client.put(f"{CELLS}/{first['id']}", headers=engineer_headers, json={"name": "nope"}).status_code == 400
        assert client.put(f"{CELLS}/{first['id']}", headers=engineer_headers, json={"name": "A2"}).status_code == 400


def get_cell(client, headers, cell_id):
    return client.get(f"{CELLS}/{cell_id}", headers=headers).json()


def of_type(client, headers, type_, query=""):
    return [c for c in client.get(f"{COMPONENTS}{query}", headers=headers).json() if c["type"] == type_]


class TestCellStatus:
    """A cell is active only while it has a cathode and an anode assigned."""

    def test_becomes_active_with_a_cathode_and_an_anode(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        create_component(client, engineer_headers, "CATHODE", "CAT-1", cell["id"])
        assert get_cell(client, engineer_headers, cell["id"])["is_active"] is False  # only a cathode
        create_component(client, engineer_headers, "ANODE", "ANO-1", cell["id"])
        assert get_cell(client, engineer_headers, cell["id"])["is_active"] is True

    def test_moving_a_component_away_deactivates_its_old_cell(self, client, engineer_headers):
        first, second = create_cell(client, engineer_headers, "A1"), create_cell(client, engineer_headers, "A2")
        equip(client, engineer_headers, first["id"])
        anode = of_type(client, engineer_headers, "ANODE", f"?cell_id={first['id']}")[0]
        client.post(f"{COMPONENTS}/{anode['id']}/assign", headers=engineer_headers, json={"cell_id": second["id"]})
        assert get_cell(client, engineer_headers, first["id"])["is_active"] is False

    def test_changing_a_component_type_updates_its_cell(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        equip(client, engineer_headers, cell["id"])
        anode = of_type(client, engineer_headers, "ANODE")[0]
        client.put(f"{COMPONENTS}/{anode['id']}", headers=engineer_headers, json={"type": "CATHODE"})
        assert get_cell(client, engineer_headers, cell["id"])["is_active"] is False

    def test_a_swap_keeps_both_cells_active(self, client, engineer_headers):
        first, second = create_cell(client, engineer_headers, "A1"), create_cell(client, engineer_headers, "A2")
        equip(client, engineer_headers, first["id"], "1")
        equip(client, engineer_headers, second["id"], "2")
        cathodes = of_type(client, engineer_headers, "CATHODE")
        client.post(
            f"{COMPONENTS}/swap",
            headers=engineer_headers,
            json={"component_a_id": cathodes[0]["id"], "component_b_id": cathodes[1]["id"]},
        )
        assert get_cell(client, engineer_headers, first["id"])["is_active"] is True
        assert get_cell(client, engineer_headers, second["id"])["is_active"] is True


class TestReleaseAndHideCell:  # US011
    def test_release_frees_the_components_and_leaves_the_cell_inactive(self, client, engineer_headers):  # E03
        cell = create_cell(client, engineer_headers)
        equip(client, engineer_headers, cell["id"])
        response = client.patch(f"{CELLS}/{cell['id']}/release", headers=engineer_headers)
        assert response.status_code == 200 and response.json()["is_active"] is False

        components = client.get(COMPONENTS, headers=engineer_headers).json()
        assert len(components) == 2
        assert all(c["cell_id"] is None and c["is_active"] for c in components)

    def test_an_inactive_cell_can_be_activated_again(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        equip(client, engineer_headers, cell["id"], "1")
        client.patch(f"{CELLS}/{cell['id']}/release", headers=engineer_headers)
        equip(client, engineer_headers, cell["id"], "2")
        assert get_cell(client, engineer_headers, cell["id"])["is_active"] is True

    def test_a_cell_with_components_cannot_be_hidden(self, client, engineer_headers):  # E02
        cell = create_cell(client, engineer_headers)
        create_component(client, engineer_headers, "CATHODE", "CAT-1", cell["id"])
        response = client.patch(f"{CELLS}/{cell['id']}/hide", headers=engineer_headers)
        assert response.status_code == 400 and "release" in response.json()["detail"]
        assert len(client.get(CELLS, headers=engineer_headers).json()) == 1

    def test_hiding_removes_it_from_the_list_but_keeps_the_record(self, client, engineer_headers):  # E01
        cell = create_cell(client, engineer_headers)
        assert client.patch(f"{CELLS}/{cell['id']}/hide", headers=engineer_headers).status_code == 200
        assert client.get(CELLS, headers=engineer_headers).json() == []
        assert client.get(f"{CELLS}/{cell['id']}", headers=engineer_headers).status_code == 200

    def test_creating_a_hidden_cell_again_brings_it_back(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers, "A3")
        client.patch(f"{CELLS}/{cell['id']}/hide", headers=engineer_headers)

        response = client.post(CELLS, headers=engineer_headers, json={"name": "a3"})
        assert response.status_code == 201
        assert (response.json()["id"], response.json()["is_active"]) == (cell["id"], False)
        assert [c["name"] for c in client.get(CELLS, headers=engineer_headers).json()] == ["A3"]

    def test_a_hidden_cell_takes_no_components(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        client.patch(f"{CELLS}/{cell['id']}/hide", headers=engineer_headers)
        response = client.post(
            COMPONENTS, headers=engineer_headers, json={"type": "ANODE", "serial_code": "A-1", "cell_id": cell["id"]}
        )
        assert response.status_code == 400


class TestBarcode:  # US016
    def test_generates_the_barcode_when_the_cell_has_cathode_and_anode(self, client, engineer_headers):  # E01
        cell = create_cell(client, engineer_headers)
        equip(client, engineer_headers, cell["id"])
        response = client.post(f"{CELLS}/{cell['id']}/barcode", headers=engineer_headers)
        assert response.status_code == 200
        assert response.json()["barcode_value"] == f"CELL-{cell['id']:05d}"
        assert client.get(f"{CELLS}/{cell['id']}", headers=engineer_headers).json()["barcode_value"] is not None

    def test_generating_again_returns_the_same_barcode(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        equip(client, engineer_headers, cell["id"])
        first = client.post(f"{CELLS}/{cell['id']}/barcode", headers=engineer_headers).json()
        second = client.post(f"{CELLS}/{cell['id']}/barcode", headers=engineer_headers).json()
        assert first["barcode_value"] == second["barcode_value"]

    def test_rejects_a_cell_without_components(self, client, engineer_headers):  # E02
        cell = create_cell(client, engineer_headers)
        response = client.post(f"{CELLS}/{cell['id']}/barcode", headers=engineer_headers)
        assert response.status_code == 400 and "cathode and anode" in response.json()["detail"]

    def test_rejects_a_cell_with_only_a_cathode(self, client, engineer_headers):  # E02
        cell = create_cell(client, engineer_headers)
        create_component(client, engineer_headers, "CATHODE", "CAT-1", cell["id"])
        assert client.post(f"{CELLS}/{cell['id']}/barcode", headers=engineer_headers).status_code == 400

    def test_barcodes_are_unique_per_cell(self, client, engineer_headers):
        first, second = create_cell(client, engineer_headers, "A1"), create_cell(client, engineer_headers, "A2")
        equip(client, engineer_headers, first["id"], "1")
        equip(client, engineer_headers, second["id"], "2")
        codes = {
            client.post(f"{CELLS}/{cell['id']}/barcode", headers=engineer_headers).json()["barcode_value"]
            for cell in (first, second)
        }
        assert len(codes) == 2
