from tests.conftest import API, ENGINEER_PASSWORD, bearer, login


def register(client, email, full_name="Pending Engineer"):
    response = client.post(
        f"{API}/auth/register", json={"full_name": full_name, "email": email, "password": ENGINEER_PASSWORD}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def review(client, headers, user_id, decision, **extra):
    return client.patch(f"{API}/users/{user_id}/approval", headers=headers, json={"decision": decision, **extra})


class TestPendingRequests:  # US018
    def test_lists_only_the_pending_requests(self, client, supervisor_headers):
        pending_id = register(client, "pending@voltcast.com")
        rejected_id = register(client, "rejected@voltcast.com")
        review(client, supervisor_headers, rejected_id, "reject")

        response = client.get(f"{API}/users?status=pending", headers=supervisor_headers)
        assert response.status_code == 200
        assert [user["id"] for user in response.json()] == [pending_id]

    def test_returns_an_empty_list_when_nothing_is_pending(self, client, supervisor_headers):
        response = client.get(f"{API}/users?status=pending", headers=supervisor_headers)
        assert response.status_code == 200 and response.json() == []

    def test_without_filter_lists_every_account(self, client, supervisor_headers):
        register(client, "pending@voltcast.com")
        assert len(client.get(f"{API}/users", headers=supervisor_headers).json()) == 2  # supervisor + pending

    def test_invalid_status_filter_is_rejected(self, client, supervisor_headers):
        assert client.get(f"{API}/users?status=banana", headers=supervisor_headers).status_code == 422


class TestAccessControl:
    def test_user_endpoints_require_authentication(self, client):
        assert client.get(f"{API}/users").status_code in (401, 403)

    def test_engineers_cannot_use_the_supervisor_endpoints(self, client, register_engineer):
        _, headers = register_engineer()
        assert client.get(f"{API}/users", headers=headers).status_code == 403
        assert client.get(f"{API}/users/1", headers=headers).status_code == 403
        assert review(client, headers, 1, "approve").status_code == 403
        assert client.put(f"{API}/users/1", headers=headers, json={"full_name": "Hacked"}).status_code == 403
        assert client.patch(f"{API}/users/1/status", headers=headers, json={"status": "disabled"}).status_code == 403


class TestApproval:  # US019
    def test_approving_activates_the_account_and_assigns_the_default_role(self, client, supervisor_headers):
        user_id = register(client, "new@voltcast.com")
        response = review(client, supervisor_headers, user_id, "approve")
        assert response.status_code == 200
        assert (response.json()["status"], response.json()["role"]) == ("active", "USER")
        assert login(client, "new@voltcast.com", ENGINEER_PASSWORD).status_code == 200

    def test_supervisor_can_choose_the_role_on_approval(self, client, supervisor_headers):
        user_id = register(client, "boss@voltcast.com")
        response = review(client, supervisor_headers, user_id, "approve", role="ADMIN")
        assert response.json()["role"] == "ADMIN"

    def test_rejecting_denies_the_access_and_keeps_the_record(self, client, supervisor_headers):
        user_id = register(client, "new@voltcast.com")
        response = review(client, supervisor_headers, user_id, "reject")
        assert (response.json()["status"], response.json()["role"]) == ("rejected", None)
        assert login(client, "new@voltcast.com", ENGINEER_PASSWORD).status_code == 401

    def test_a_request_cannot_be_reviewed_twice(self, client, supervisor_headers):
        user_id = register(client, "new@voltcast.com")
        assert review(client, supervisor_headers, user_id, "approve").status_code == 200
        assert review(client, supervisor_headers, user_id, "approve").status_code == 400
        assert review(client, supervisor_headers, user_id, "reject").status_code == 400

    def test_invalid_decision_is_rejected(self, client, supervisor_headers):
        user_id = register(client, "new@voltcast.com")
        assert review(client, supervisor_headers, user_id, "maybe").status_code == 422

    def test_unknown_user_returns_404(self, client, supervisor_headers):
        assert review(client, supervisor_headers, 99, "approve").status_code == 404
        assert client.get(f"{API}/users/99", headers=supervisor_headers).status_code == 404


class TestAccountManagement:  # US020
    def test_supervisor_edits_the_data_of_an_engineer(self, client, supervisor_headers, register_engineer):
        user_id, _ = register_engineer()
        response = client.put(
            f"{API}/users/{user_id}",
            headers=supervisor_headers,
            json={"full_name": "Nombre Corregido", "email": "Nuevo@VoltCast.com"},
        )
        assert response.status_code == 200
        assert (response.json()["full_name"], response.json()["email"]) == ("Nombre Corregido", "nuevo@voltcast.com")
        assert login(client, "nuevo@voltcast.com", ENGINEER_PASSWORD).status_code == 200

    def test_cannot_move_an_account_to_an_email_that_is_taken(self, client, supervisor_headers, register_engineer):
        user_id, _ = register_engineer("one@voltcast.com")
        register_engineer("two@voltcast.com")
        response = client.put(f"{API}/users/{user_id}", headers=supervisor_headers, json={"email": "two@voltcast.com"})
        assert response.status_code == 400

    def test_disabling_cuts_the_access_immediately_even_with_a_valid_token(
        self, client, supervisor_headers, register_engineer
    ):
        user_id, engineer_headers = register_engineer()
        assert client.get(f"{API}/auth/me", headers=engineer_headers).status_code == 200

        response = client.patch(f"{API}/users/{user_id}/status", headers=supervisor_headers, json={"status": "disabled"})
        assert response.status_code == 200 and response.json()["status"] == "disabled"

        assert client.get(f"{API}/auth/me", headers=engineer_headers).status_code == 401
        denied = login(client, "engineer@voltcast.com", ENGINEER_PASSWORD)
        assert denied.status_code == 401 and "disabled" in denied.json()["detail"]

    def test_a_disabled_account_can_be_enabled_again(self, client, supervisor_headers, register_engineer):
        user_id, _ = register_engineer()
        client.patch(f"{API}/users/{user_id}/status", headers=supervisor_headers, json={"status": "disabled"})
        response = client.patch(f"{API}/users/{user_id}/status", headers=supervisor_headers, json={"status": "active"})
        assert response.json()["status"] == "active"
        assert login(client, "engineer@voltcast.com", ENGINEER_PASSWORD).status_code == 200

    def test_status_changes_must_follow_the_account_lifecycle(self, client, supervisor_headers, register_engineer):
        user_id, _ = register_engineer()
        already_active = client.patch(f"{API}/users/{user_id}/status", headers=supervisor_headers, json={"status": "active"})
        assert already_active.status_code == 400
        client.patch(f"{API}/users/{user_id}/status", headers=supervisor_headers, json={"status": "disabled"})
        twice = client.patch(f"{API}/users/{user_id}/status", headers=supervisor_headers, json={"status": "disabled"})
        assert twice.status_code == 400

    def test_supervisor_accounts_cannot_be_edited_or_disabled(self, client, supervisor_headers):
        supervisor_id = client.get(f"{API}/auth/me", headers=supervisor_headers).json()["id"]
        disable = client.patch(f"{API}/users/{supervisor_id}/status", headers=supervisor_headers, json={"status": "disabled"})
        edit = client.put(f"{API}/users/{supervisor_id}", headers=supervisor_headers, json={"full_name": "Otro Nombre"})
        assert disable.status_code == edit.status_code == 400

    def test_pending_requests_cannot_be_edited_or_disabled(self, client, supervisor_headers):
        user_id = register(client, "new@voltcast.com")
        assert client.put(f"{API}/users/{user_id}", headers=supervisor_headers, json={"full_name": "Otro"}).status_code == 400
        disable = client.patch(f"{API}/users/{user_id}/status", headers=supervisor_headers, json={"status": "disabled"})
        assert disable.status_code == 400

    def test_unknown_user_returns_404(self, client, supervisor_headers):
        assert client.put(f"{API}/users/99", headers=supervisor_headers, json={"full_name": "Nadie Mas"}).status_code == 404
        assert client.patch(f"{API}/users/99/status", headers=supervisor_headers, json={"status": "disabled"}).status_code == 404
