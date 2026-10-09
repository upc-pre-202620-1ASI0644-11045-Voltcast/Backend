from tests.conftest import (
    API, ENGINEER_PASSWORD, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD, bearer, login,
)

REGISTER = f"{API}/auth/register"


def register(client, email="juan@voltcast.com", password=ENGINEER_PASSWORD, full_name="Juan Perez"):
    return client.post(REGISTER, json={"full_name": full_name, "email": email, "password": password})


class TestRegister:  # US023
    def test_creates_a_pending_request_without_role(self, client):
        response = register(client, email="Juan@VoltCast.com")
        assert response.status_code == 201
        body = response.json()
        assert (body["email"], body["status"], body["role"]) == ("juan@voltcast.com", "pending", None)
        assert "password" not in body and "hashed_password" not in body

    def test_rejects_missing_required_fields_listing_them(self, client):
        response = client.post(REGISTER, json={"email": "juan@voltcast.com"})
        assert response.status_code == 422
        missing = {error["loc"][-1] for error in response.json()["detail"]}
        assert missing == {"full_name", "password"}

    def test_rejects_an_invalid_email(self, client):
        assert register(client, email="not-an-email").status_code == 422

    def test_rejects_a_password_that_breaks_the_policy(self, client):
        response = register(client, password="weakpass1")
        assert response.status_code == 400
        assert "uppercase" in response.json()["detail"]

    def test_rejects_a_duplicated_email(self, client):
        assert register(client).status_code == 201
        response = register(client, email="JUAN@voltcast.com")
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_a_rejected_applicant_can_apply_again_reusing_the_same_row(self, client, supervisor_headers):
        first_id = register(client).json()["id"]
        client.patch(f"{API}/users/{first_id}/approval", headers=supervisor_headers, json={"decision": "reject"})

        response = register(client, full_name="Juan P. Corregido")
        assert response.status_code == 201
        assert response.json()["id"] == first_id
        assert response.json()["status"] == "pending"


class TestLogin:  # US021
    def test_supervisor_logs_in_and_receives_tokens_and_role(self, client):
        response = login(client, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD)
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["access_token"] and body["refresh_token"]
        assert (body["user"]["role"], body["user"]["status"]) == ("ADMIN", "active")

    def test_email_is_case_insensitive(self, client):
        assert login(client, SUPERVISOR_EMAIL.upper(), SUPERVISOR_PASSWORD).status_code == 200

    def test_wrong_password_and_unknown_email_get_the_same_message(self, client):
        wrong_password = login(client, SUPERVISOR_EMAIL, "Wrong#Pass1")
        unknown_email = login(client, "nobody@voltcast.com", "Wrong#Pass1")
        assert wrong_password.status_code == unknown_email.status_code == 401
        assert wrong_password.json() == unknown_email.json() == {"detail": "Invalid credentials"}

    def test_pending_account_cannot_log_in(self, client):
        register(client)
        response = login(client, "juan@voltcast.com", ENGINEER_PASSWORD)
        assert response.status_code == 401
        assert "pending approval" in response.json()["detail"]

    def test_rejected_account_cannot_log_in(self, client, supervisor_headers):
        user_id = register(client).json()["id"]
        client.patch(f"{API}/users/{user_id}/approval", headers=supervisor_headers, json={"decision": "reject"})
        response = login(client, "juan@voltcast.com", ENGINEER_PASSWORD)
        assert response.status_code == 401
        assert "rejected" in response.json()["detail"]

    def test_wrong_password_never_reveals_the_account_status(self, client):
        register(client)
        response = login(client, "juan@voltcast.com", "Wrong#Pass1")
        assert response.json() == {"detail": "Invalid credentials"}


class TestTokens:
    def test_me_returns_the_authenticated_user(self, client, supervisor_headers):
        response = client.get(f"{API}/auth/me", headers=supervisor_headers)
        assert response.status_code == 200
        assert response.json()["email"] == SUPERVISOR_EMAIL

    def test_protected_endpoints_require_a_token(self, client):
        assert client.get(f"{API}/auth/me").status_code in (401, 403)

    def test_garbage_token_is_rejected(self, client):
        assert client.get(f"{API}/auth/me", headers=bearer("not.a.jwt")).status_code == 401

    def test_refresh_token_is_not_accepted_as_access_token(self, client):
        refresh = login(client, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD).json()["refresh_token"]
        assert client.get(f"{API}/auth/me", headers=bearer(refresh)).status_code == 401

    def test_refresh_issues_a_new_access_token(self, client):
        refresh = login(client, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD).json()["refresh_token"]
        response = client.post(f"{API}/auth/refresh", json={"refresh_token": refresh})
        assert response.status_code == 200
        assert client.get(f"{API}/auth/me", headers=bearer(response.json()["access_token"])).status_code == 200

    def test_access_token_is_not_accepted_for_refreshing(self, client):
        access = login(client, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD).json()["access_token"]
        assert client.post(f"{API}/auth/refresh", json={"refresh_token": access}).status_code == 401
