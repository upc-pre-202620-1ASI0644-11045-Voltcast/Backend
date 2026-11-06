from sqlalchemy import select

from notification_management.domain.model.aggregates.Notification import Notification, NotificationStatus
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from tests.conftest import API, ENGINEER_PASSWORD, SUPERVISOR_EMAIL

EMAIL = "engineer@voltcast.com"


def register(client, email=EMAIL):
    return client.post(f"{API}/auth/register", json={"full_name": "Test Engineer", "email": email, "password": ENGINEER_PASSWORD})


def review(client, headers, user_id, decision):
    return client.patch(f"{API}/users/{user_id}/approval", headers=headers, json={"decision": decision})


def statuses(client) -> list[NotificationStatus]:
    async def read():
        async with AsyncSessionLocal() as session:
            return list((await session.execute(select(Notification.status).order_by(Notification.id))).scalars())

    return client.portal.call(read)


class TestAccessRequest:  # US025
    def test_supervisor_is_notified_of_a_new_request(self, client, sent_emails):
        assert register(client).status_code == 201
        assert sent_emails == [(SUPERVISOR_EMAIL, "Nueva solicitud de registro")]
        assert statuses(client) == [NotificationStatus.SENT]

    def test_invalid_request_notifies_nobody(self, client, sent_emails):
        assert register(client, "not-an-email").status_code == 422
        assert sent_emails == []


class TestAccountReview:  # US029, US030
    def test_engineer_is_told_the_account_was_accepted(self, client, supervisor_headers, sent_emails):
        user_id = register(client).json()["id"]
        sent_emails.clear()
        assert review(client, supervisor_headers, user_id, "approve").status_code == 200
        assert sent_emails == [(EMAIL, "Tu cuenta fue aceptada")]

    def test_engineer_is_told_the_account_was_rejected(self, client, supervisor_headers, sent_emails):
        user_id = register(client).json()["id"]
        sent_emails.clear()
        assert review(client, supervisor_headers, user_id, "reject").status_code == 200
        assert sent_emails == [(EMAIL, "Tu cuenta fue rechazada")]

    def test_a_failed_send_stays_pending_and_goes_out_later(self, client, supervisor_headers, sent_emails, monkeypatch):
        user_id = register(client).json()["id"]
        working_send = "shared.infrastructure.email.email_client.send_email"

        async def offline(to, subject, body_html):
            raise ConnectionError("no connection")

        monkeypatch.setattr(working_send, offline)
        assert review(client, supervisor_headers, user_id, "approve").status_code == 200  # the approval is not lost
        assert statuses(client)[-1] == NotificationStatus.PENDING

        async def online(to, subject, body_html):
            sent_emails.append((to, subject))

        monkeypatch.setattr(working_send, online)
        sent_emails.clear()
        register(client, "other@voltcast.com")  # any later event sends the pending ones first
        assert (EMAIL, "Tu cuenta fue aceptada") in sent_emails
        assert NotificationStatus.PENDING not in statuses(client)


class TestScheduledDispatch:  # US029, US030 E02: the scheduled Job sends what stayed pending
    def test_the_notifications_task_sends_the_pending_emails(self, client, supervisor_headers, sent_emails, monkeypatch):
        from worker.main import run

        user_id = register(client).json()["id"]

        async def offline(to, subject, body_html):
            raise ConnectionError("no connection")

        online = "shared.infrastructure.email.email_client.send_email"
        monkeypatch.setattr(online, offline)
        review(client, supervisor_headers, user_id, "approve")
        assert statuses(client)[-1] == NotificationStatus.PENDING

        async def back_online(to, subject, body_html):
            sent_emails.append((to, subject))

        monkeypatch.setattr(online, back_online)
        sent_emails.clear()
        assert client.portal.call(run, "notifications") is True
        assert (EMAIL, "Tu cuenta fue aceptada") in sent_emails
        assert NotificationStatus.PENDING not in statuses(client)
