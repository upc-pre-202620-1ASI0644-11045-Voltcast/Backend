from datetime import timedelta

from sqlalchemy import update

from iam.domain.model.aggregates.PasswordReset import PasswordReset, utc_now_naive
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from tests.conftest import API, ENGINEER_PASSWORD, login

EMAIL = "engineer@voltcast.com"
NEW_PASSWORD = "Brand#New1"


def request_code(client, email=EMAIL):
    return client.post(f"{API}/auth/password-reset/request", json={"email": email})


def confirm(client, code, new_password=NEW_PASSWORD, email=EMAIL):
    return client.post(
        f"{API}/auth/password-reset/confirm", json={"email": email, "code": code, "new_password": new_password}
    )


def wrong_code(code: str) -> str:
    return "000000" if code != "000000" else "111111"


class TestRequestCode:  # US022 E01
    def test_sends_a_code_to_a_registered_email(self, client, register_engineer, sent_codes):
        register_engineer()
        assert request_code(client).status_code == 200
        assert len(sent_codes[EMAIL]) == 6

    def test_does_not_reveal_whether_the_email_exists(self, client, register_engineer, sent_codes):
        register_engineer()
        known = request_code(client)
        unknown = request_code(client, "nobody@voltcast.com")
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        assert "nobody@voltcast.com" not in sent_codes

    def test_no_code_is_sent_to_accounts_that_cannot_log_in(self, client, sent_codes):
        client.post(f"{API}/auth/register", json={"full_name": "Pending One", "email": EMAIL, "password": ENGINEER_PASSWORD})
        assert request_code(client).status_code == 200
        assert sent_codes == {}


class TestConfirmCode:
    def test_sets_the_new_password(self, client, register_engineer, sent_codes):
        register_engineer()
        request_code(client)
        assert confirm(client, sent_codes[EMAIL]).status_code == 200
        assert login(client, EMAIL, NEW_PASSWORD).status_code == 200
        assert login(client, EMAIL, ENGINEER_PASSWORD).status_code == 401

    def test_wrong_code_is_rejected(self, client, register_engineer, sent_codes):  # US022 E02
        register_engineer()
        request_code(client)
        response = confirm(client, wrong_code(sent_codes[EMAIL]))
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]
        assert login(client, EMAIL, ENGINEER_PASSWORD).status_code == 200

    def test_expired_code_is_rejected(self, client, register_engineer, sent_codes):  # US022 E02
        register_engineer()
        request_code(client)

        async def expire_codes():
            async with AsyncSessionLocal() as session:
                await session.execute(update(PasswordReset).values(expires_at=utc_now_naive() - timedelta(minutes=1)))
                await session.commit()

        client.portal.call(expire_codes)
        response = confirm(client, sent_codes[EMAIL])
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]

    def test_a_code_can_only_be_used_once(self, client, register_engineer, sent_codes):
        register_engineer()
        request_code(client)
        code = sent_codes[EMAIL]
        assert confirm(client, code).status_code == 200
        assert confirm(client, code, new_password="Another#Pass1").status_code == 400

    def test_the_new_password_must_follow_the_policy_and_the_code_stays_valid(
        self, client, register_engineer, sent_codes
    ):
        register_engineer()
        request_code(client)
        code = sent_codes[EMAIL]
        weak = confirm(client, code, new_password="alllowercase1")
        assert weak.status_code == 400 and "uppercase" in weak.json()["detail"]
        assert confirm(client, code).status_code == 200

    def test_unknown_email_gets_the_same_error_as_a_wrong_code(self, client, sent_codes):
        response = confirm(client, "123456", email="nobody@voltcast.com")
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]

    def test_code_must_have_six_characters(self, client):
        assert confirm(client, "123").status_code == 422


class TestSingleCodePerUser:
    def test_a_new_request_invalidates_the_previous_code(self, client, register_engineer, sent_codes):
        register_engineer()
        request_code(client)
        first = sent_codes[EMAIL]
        for _ in range(5):  # a repeated random code would make the check meaningless
            request_code(client)
            if sent_codes[EMAIL] != first:
                break
        latest = sent_codes[EMAIL]
        assert latest != first

        assert confirm(client, first).status_code == 400
        assert confirm(client, latest).status_code == 200

    def test_the_user_never_owns_more_than_one_row(self, client, register_engineer, sent_codes):
        # password_reset.id is a TINYINT: rows must be reused instead of accumulating
        user_id, _ = register_engineer()
        for _ in range(4):
            request_code(client)

        async def count_rows():
            async with AsyncSessionLocal() as session:
                from sqlalchemy import func, select
                return (await session.execute(
                    select(func.count()).select_from(PasswordReset).where(PasswordReset.user_id == user_id)
                )).scalar_one()

        assert client.portal.call(count_rows) == 1


class TestPasswordChangedEmail:  # US024
    def test_the_owner_is_notified_when_the_password_changes(self, client, register_engineer, sent_codes, sent_emails):
        register_engineer()
        request_code(client)
        sent_emails.clear()
        assert confirm(client, sent_codes[EMAIL]).status_code == 200
        assert sent_emails == [(EMAIL, "Contraseña cambiada")]

    def test_nobody_is_notified_when_the_password_is_not_valid(self, client, register_engineer, sent_codes, sent_emails):
        register_engineer()
        request_code(client)
        sent_emails.clear()
        assert confirm(client, sent_codes[EMAIL], new_password="weak").status_code in (400, 422)
        assert sent_emails == []
