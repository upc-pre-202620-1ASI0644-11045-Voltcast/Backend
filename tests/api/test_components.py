from tests.api.test_cells import CELLS, COMPONENTS, create_cell, create_component


class TestRegisterComponent:  # US012
    def test_registers_a_component_assigned_to_a_cell(self, client, engineer_headers):  # E01
        cell = create_cell(client, engineer_headers)
        response = client.post(
            COMPONENTS, headers=engineer_headers, json={"type": "CATHODE", "serial_code": "CAT-1", "cell_id": cell["id"]}
        )
        assert response.status_code == 201
        assert response.json() == {
            "id": response.json()["id"], "type": "CATHODE", "serial_code": "CAT-1", "is_active": True, "cell_id": cell["id"],
        }

    def test_the_cell_is_optional(self, client, engineer_headers):
        component = create_component(client, engineer_headers, "ANODE", "ANO-1")
        assert component["cell_id"] is None and component["type"] == "ANODE"

    def test_rejects_incomplete_data_listing_the_missing_fields(self, client, engineer_headers):  # E02
        response = client.post(COMPONENTS, headers=engineer_headers, json={})
        assert response.status_code == 422
        assert {error["loc"][-1] for error in response.json()["detail"]} == {"type", "serial_code"}

    def test_rejects_an_unknown_type(self, client, engineer_headers):
        response = client.post(COMPONENTS, headers=engineer_headers, json={"type": "BATTERY", "serial_code": "X-1"})
        assert response.status_code == 422

    def test_serial_code_must_be_unique(self, client, engineer_headers):
        create_component(client, engineer_headers, serial="CAT-1")
        response = client.post(COMPONENTS, headers=engineer_headers, json={"type": "ANODE", "serial_code": "CAT-1"})
        assert response.status_code == 400 and "already exists" in response.json()["detail"]

    def test_rejects_an_unknown_or_disabled_cell(self, client, engineer_headers):
        unknown = client.post(COMPONENTS, headers=engineer_headers, json={"type": "ANODE", "serial_code": "A-1", "cell_id": 99})
        assert unknown.status_code == 400

        cell = create_cell(client, engineer_headers)
        client.patch(f"{CELLS}/{cell['id']}/disable", headers=engineer_headers)
        disabled = client.post(
            COMPONENTS, headers=engineer_headers, json={"type": "ANODE", "serial_code": "A-2", "cell_id": cell["id"]}
        )
        assert disabled.status_code == 400 and "disabled" in disabled.json()["detail"]

    def test_requires_authentication(self, client):
        assert client.post(COMPONENTS, json={"type": "ANODE", "serial_code": "A-1"}).status_code in (401, 403)


class TestReadComponents:
    def test_filters_by_type_cell_and_status(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        create_component(client, engineer_headers, "CATHODE", "CAT-1", cell["id"])
        create_component(client, engineer_headers, "ANODE", "ANO-1", cell["id"])
        free = create_component(client, engineer_headers, "CATHODE", "CAT-2")
        client.patch(f"{COMPONENTS}/{free['id']}/disable", headers=engineer_headers)

        def serials(query):
            return sorted(c["serial_code"] for c in client.get(f"{COMPONENTS}{query}", headers=engineer_headers).json())

        assert serials("") == ["ANO-1", "CAT-1", "CAT-2"]
        assert serials("?component_type=CATHODE") == ["CAT-1", "CAT-2"]
        assert serials(f"?cell_id={cell['id']}") == ["ANO-1", "CAT-1"]
        assert serials("?is_active=false") == ["CAT-2"]

    def test_rejects_an_unknown_type_filter(self, client, engineer_headers):
        assert client.get(f"{COMPONENTS}?component_type=BATTERY", headers=engineer_headers).status_code == 422

    def test_get_by_id(self, client, engineer_headers):
        component = create_component(client, engineer_headers)
        assert client.get(f"{COMPONENTS}/{component['id']}", headers=engineer_headers).json()["serial_code"] == "CAT-1"
        assert client.get(f"{COMPONENTS}/999", headers=engineer_headers).status_code == 404


class TestEditComponent:  # US015
    def test_updates_serial_code_and_type(self, client, engineer_headers):  # E01
        component = create_component(client, engineer_headers)
        response = client.put(
            f"{COMPONENTS}/{component['id']}", headers=engineer_headers, json={"serial_code": "ANO-9", "type": "ANODE"}
        )
        assert response.status_code == 200
        assert (response.json()["serial_code"], response.json()["type"]) == ("ANO-9", "ANODE")

    def test_rejects_invalid_values(self, client, engineer_headers):  # E02
        component = create_component(client, engineer_headers)
        assert client.put(f"{COMPONENTS}/{component['id']}", headers=engineer_headers, json={"type": "BATTERY"}).status_code == 422
        assert client.put(f"{COMPONENTS}/{component['id']}", headers=engineer_headers, json={"serial_code": ""}).status_code == 422

    def test_rejects_a_serial_code_used_by_another_component(self, client, engineer_headers):
        create_component(client, engineer_headers, serial="CAT-1")
        other = create_component(client, engineer_headers, "ANODE", "ANO-1")
        response = client.put(f"{COMPONENTS}/{other['id']}", headers=engineer_headers, json={"serial_code": "CAT-1"})
        assert response.status_code == 400

    def test_keeping_the_same_serial_code_is_allowed(self, client, engineer_headers):
        component = create_component(client, engineer_headers)
        response = client.put(f"{COMPONENTS}/{component['id']}", headers=engineer_headers, json={"serial_code": "CAT-1"})
        assert response.status_code == 200


class TestDisableComponent:  # US013
    def test_disables_a_component_that_is_not_in_use(self, client, engineer_headers):  # E01
        component = create_component(client, engineer_headers)
        response = client.patch(f"{COMPONENTS}/{component['id']}/disable", headers=engineer_headers)
        assert response.status_code == 200 and response.json()["is_active"] is False

    def test_rejects_a_component_assigned_to_a_cell(self, client, engineer_headers):  # E02
        cell = create_cell(client, engineer_headers)
        component = create_component(client, engineer_headers, cell_id=cell["id"])
        response = client.patch(f"{COMPONENTS}/{component['id']}/disable", headers=engineer_headers)
        assert response.status_code == 400 and "in use" in response.json()["detail"]
        still = client.get(f"{COMPONENTS}/{component['id']}", headers=engineer_headers).json()
        assert still["is_active"] is True and still["cell_id"] == cell["id"]

    def test_can_be_disabled_after_being_released_from_its_cell(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        component = create_component(client, engineer_headers, cell_id=cell["id"])
        client.patch(f"{CELLS}/{cell['id']}/disable?release_components=true", headers=engineer_headers)
        assert client.patch(f"{COMPONENTS}/{component['id']}/disable", headers=engineer_headers).status_code == 200

    def test_a_disabled_component_cannot_be_assigned(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        component = create_component(client, engineer_headers)
        client.patch(f"{COMPONENTS}/{component['id']}/disable", headers=engineer_headers)
        response = client.post(f"{COMPONENTS}/{component['id']}/assign", headers=engineer_headers, json={"cell_id": cell["id"]})
        assert response.status_code == 400


class TestAssignComponent:
    def test_assigns_a_free_component_to_a_cell(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        component = create_component(client, engineer_headers)
        response = client.post(f"{COMPONENTS}/{component['id']}/assign", headers=engineer_headers, json={"cell_id": cell["id"]})
        assert response.status_code == 200 and response.json()["cell_id"] == cell["id"]

    def test_rejects_an_unknown_or_disabled_cell(self, client, engineer_headers):
        component = create_component(client, engineer_headers)
        assert client.post(f"{COMPONENTS}/{component['id']}/assign", headers=engineer_headers, json={"cell_id": 99}).status_code == 400

        cell = create_cell(client, engineer_headers)
        client.patch(f"{CELLS}/{cell['id']}/disable", headers=engineer_headers)
        response = client.post(f"{COMPONENTS}/{component['id']}/assign", headers=engineer_headers, json={"cell_id": cell["id"]})
        assert response.status_code == 400


class TestSwapComponents:  # US014
    def swap(self, client, headers, first_id, second_id):
        return client.post(f"{COMPONENTS}/swap", headers=headers, json={"component_a_id": first_id, "component_b_id": second_id})

    def test_swaps_two_components_between_their_cells(self, client, engineer_headers):  # E01
        cell_a, cell_b = create_cell(client, engineer_headers, "A1"), create_cell(client, engineer_headers, "A2")
        cathode_a = create_component(client, engineer_headers, "CATHODE", "CAT-A", cell_a["id"])
        cathode_b = create_component(client, engineer_headers, "CATHODE", "CAT-B", cell_b["id"])

        response = self.swap(client, engineer_headers, cathode_a["id"], cathode_b["id"])
        assert response.status_code == 200
        assert [c["cell_id"] for c in response.json()] == [cell_b["id"], cell_a["id"]]

        in_a = client.get(f"{COMPONENTS}?cell_id={cell_a['id']}", headers=engineer_headers).json()
        in_b = client.get(f"{COMPONENTS}?cell_id={cell_b['id']}", headers=engineer_headers).json()
        assert [c["serial_code"] for c in in_a] == ["CAT-B"]
        assert [c["serial_code"] for c in in_b] == ["CAT-A"]

    def test_only_components_of_the_same_type_can_be_swapped(self, client, engineer_headers):
        cell_a, cell_b = create_cell(client, engineer_headers, "A1"), create_cell(client, engineer_headers, "A2")
        cathode = create_component(client, engineer_headers, "CATHODE", "CAT-A", cell_a["id"])
        anode = create_component(client, engineer_headers, "ANODE", "ANO-B", cell_b["id"])
        response = self.swap(client, engineer_headers, cathode["id"], anode["id"])
        assert response.status_code == 400 and "same type" in response.json()["detail"]

    def test_both_components_must_be_assigned_to_a_cell(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        assigned = create_component(client, engineer_headers, "CATHODE", "CAT-A", cell["id"])
        free = create_component(client, engineer_headers, "CATHODE", "CAT-B")
        assert self.swap(client, engineer_headers, assigned["id"], free["id"]).status_code == 400
        still = client.get(f"{COMPONENTS}/{assigned['id']}", headers=engineer_headers).json()
        assert still["cell_id"] == cell["id"]

    def test_components_of_the_same_cell_cannot_be_swapped(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        first = create_component(client, engineer_headers, "CATHODE", "CAT-A", cell["id"])
        second = create_component(client, engineer_headers, "CATHODE", "CAT-B", cell["id"])
        assert self.swap(client, engineer_headers, first["id"], second["id"]).status_code == 400

    def test_unknown_component_is_rejected(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)
        component = create_component(client, engineer_headers, "CATHODE", "CAT-A", cell["id"])
        assert self.swap(client, engineer_headers, component["id"], 99).status_code == 400
