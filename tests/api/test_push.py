from sqlalchemy import select

from notification_management.domain.model.aggregates.DeviceToken import DeviceToken
from notification_management.domain.model.aggregates.Notification import Notification, NotificationChannel, NotificationStatus
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from tests.api.test_notifications import register
from tests.api.test_training import ALERT_RULES, cleaned_dataset, force_limit, request_training, run_training
from tests.conftest import API
from worker.main import run

NOTIFICATIONS = f"{API}/notifications"
TOKEN = "t" * 40
OTHER_TOKEN = "o" * 40


def db(client, fn):
    async def run_query():
        async with AsyncSessionLocal() as session:
            return await fn(session)

    return client.portal.call(run_query)


def push_statuses(client) -> list[NotificationStatus]:
    async def read(session):
        rows = await session.execute(
            select(Notification.status).where(Notification.channel == NotificationChannel.PUSH).order_by(Notification.id)
        )
        return list(rows.scalars())

    return db(client, read)


def add_device(client, headers, token=TOKEN):
    return client.post(f"{NOTIFICATIONS}/devices", headers=headers, json={"token": token})


class TestInbox:
    def test_the_supervisor_reads_the_access_request(self, client, supervisor_headers):
        register(client)
        items = client.get(NOTIFICATIONS, headers=supervisor_headers).json()
        assert [(n["type"], n["title"], n["body"]) for n in items] == [
            ("R", "Nueva solicitud de registro", "Hay una nueva solicitud de acceso pendiente de revisión")
        ]

    def test_the_account_decision_is_email_only_so_the_engineer_inbox_is_empty(self, client, register_engineer):
        _, headers = register_engineer()
        assert client.get(NOTIFICATIONS, headers=headers).json() == []

    def test_the_inbox_requires_a_token(self, client):
        assert client.get(NOTIFICATIONS).status_code in (401, 403)

    def test_can_be_filtered_by_status(self, client, supervisor_headers):
        register(client)
        assert len(client.get(NOTIFICATIONS, headers=supervisor_headers, params={"status": "sent"}).json()) == 1
        assert client.get(NOTIFICATIONS, headers=supervisor_headers, params={"status": "read"}).json() == []
        assert client.get(NOTIFICATIONS, headers=supervisor_headers, params={"status": "nope"}).status_code == 422


class TestMarkRead:
    def test_marks_my_notification_as_read(self, client, supervisor_headers):
        register(client)
        notification_id = client.get(NOTIFICATIONS, headers=supervisor_headers).json()[0]["id"]
        assert client.patch(f"{NOTIFICATIONS}/{notification_id}/read", headers=supervisor_headers).status_code == 204
        read = client.get(NOTIFICATIONS, headers=supervisor_headers, params={"status": "read"}).json()
        assert [n["id"] for n in read] == [notification_id]

    def test_cannot_touch_the_notification_of_someone_else(self, client, supervisor_headers, register_engineer):
        register(client)
        notification_id = client.get(NOTIFICATIONS, headers=supervisor_headers).json()[0]["id"]
        _, engineer = register_engineer("another@voltcast.com")
        assert client.patch(f"{NOTIFICATIONS}/{notification_id}/read", headers=engineer).status_code == 404
        assert client.patch(f"{NOTIFICATIONS}/9999/read", headers=engineer).status_code == 404


class TestDevices:
    def test_registers_a_phone_once(self, client, supervisor_headers):
        first = add_device(client, supervisor_headers)
        assert first.status_code == 201
        assert add_device(client, supervisor_headers).json() == first.json()

    def test_a_phone_that_changes_hands_goes_to_the_new_user(self, client, supervisor_headers, register_engineer):
        user_id, engineer = register_engineer()
        add_device(client, supervisor_headers)
        add_device(client, engineer)

        async def owners(session):
            return [d.user_id for d in (await session.execute(select(DeviceToken))).scalars()]

        assert db(client, owners) == [user_id]

    def test_unregisters_only_my_own_phones(self, client, supervisor_headers, engineer_headers):
        device_id = add_device(client, supervisor_headers).json()["id"]
        assert client.delete(f"{NOTIFICATIONS}/devices/{device_id}", headers=engineer_headers).status_code == 404
        assert client.delete(f"{NOTIFICATIONS}/devices/{device_id}", headers=supervisor_headers).status_code == 204
        assert client.delete(f"{NOTIFICATIONS}/devices/{device_id}", headers=supervisor_headers).status_code == 404

    def test_rejects_a_token_that_cannot_be_real(self, client, supervisor_headers):
        assert add_device(client, supervisor_headers, token="short").status_code == 422


class TestPushDelivery:
    def test_the_phone_of_the_supervisor_gets_the_access_request(self, client, supervisor_headers, fake_push):
        add_device(client, supervisor_headers)
        register(client)
        [(tokens, title, body, data)] = fake_push.calls
        assert tokens == [TOKEN] and title == "Nueva solicitud de registro" and "solicitud de acceso" in body
        assert data["notification_id"].isdigit()
        assert push_statuses(client) == [NotificationStatus.SENT]

    def test_a_user_without_phones_gets_the_inbox_only(self, client, fake_push):
        register(client)
        assert fake_push.calls == []
        assert push_statuses(client) == [NotificationStatus.SENT]

    def test_forgets_the_tokens_fcm_refuses(self, client, supervisor_headers, fake_push):
        add_device(client, supervisor_headers)
        fake_push.invalid = [TOKEN]
        register(client)

        async def count(session):
            return len((await session.execute(select(DeviceToken))).scalars().all())

        assert db(client, count) == 0

    def test_a_push_that_fails_stays_pending_and_the_job_sends_it(self, client, supervisor_headers, fake_push):
        add_device(client, supervisor_headers)
        fake_push.fail = True
        register(client)
        assert push_statuses(client) == [NotificationStatus.PENDING]
        fake_push.fail = False
        assert client.portal.call(run, "notifications") is True
        assert push_statuses(client) == [NotificationStatus.SENT]
        assert len(fake_push.calls) == 1

    def test_the_voltage_alerts_go_out_as_one_push_per_user(self, client, supervisor_headers, register_engineer, fake_push):
        _, engineer = register_engineer()
        add_device(client, engineer, OTHER_TOKEN)
        force_limit(client, 1.0)
        request_training(client, engineer, cleaned_dataset(client, engineer))
        run_training(client)  # the training pushes the alerts itself
        assert {call[1] for call in fake_push.calls} == {"Voltaje excesivo pronosticado"}
        assert len(fake_push.calls) == 1 and "5 avisos nuevos" in fake_push.calls[0][2]  # one push, not one per cell

    def test_the_training_pushes_its_alerts_right_away_and_a_push_failure_does_not_fail_it(
        self, client, supervisor_headers, register_engineer, fake_push
    ):
        _, engineer = register_engineer()
        add_device(client, engineer, OTHER_TOKEN)
        force_limit(client, 1.0)
        fake_push.calls.clear()
        request_training(client, engineer, cleaned_dataset(client, engineer))
        run_training(client)  # no scheduled Job in between
        assert len(fake_push.calls) == 1

        fake_push.fail = True
        request_training(client, engineer, cleaned_dataset(client, engineer))
        assert run_training(client) is True  # the model is published, the alerts stay pending for the Job
