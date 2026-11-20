from datetime import datetime

import pytest
from sqlalchemy import func, select, update

from notification_management.domain.model.aggregates.Notification import (
    DATE_NEAR,
    DATE_NEAR_2_DAYS,
    VOLTAGE_EXCEEDED,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from notification_management.interface.notifier import notifier_for
from tests.conftest import API
from tests.api.test_push import add_device
from tests.api.test_training import (  # noqa: F401  small_network is an autouse fixture
    ALERT_RULES,
    cleaned_dataset,
    db,
    force_limit,
    request_training,
    run_training,
    small_network,
)
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction
from worker.tasks.voltage_alerts import remind_near_exceedances

CELLS = 5  # the synthetic workbooks of the training tests have 5 cells


def alerts(client, code: str, channel: NotificationChannel = NotificationChannel.PUSH) -> list:
    """The rows of an alert in one channel: every alert is queued once per cell as a push row and as an email row."""
    async def read(session):
        rows = await session.execute(
            select(Notification).join(NotificationType)
            .where(NotificationType.type == code, Notification.channel == channel).order_by(Notification.id)
        )
        return list(rows.scalars().unique())

    return db(client, read)


@pytest.fixture
def mails(monkeypatch) -> list[tuple[str, str, str]]:
    """The (recipient, subject, html) of every email sent."""
    sent: list[tuple[str, str, str]] = []

    async def fake_send(to: str, subject: str, body_html: str) -> None:
        sent.append((to, subject, body_html))

    monkeypatch.setattr("shared.infrastructure.email.email_client.send_email", fake_send)
    return sent


def train(client, headers):
    request_training(client, headers, cleaned_dataset(client, headers))
    run_training(client)


class TestVoltageExceeded:  # US026
    def test_every_engineer_is_told_per_cell_of_the_first_day_above_the_limit(
        self, client, engineer_headers, supervisor_headers
    ):
        force_limit(client, 1.0)  # below any real voltage
        train(client, engineer_headers)
        rows = alerts(client, VOLTAGE_EXCEEDED)
        assert len(rows) == CELLS
        assert {(r.channel, r.status) for r in rows} == {(NotificationChannel.PUSH, NotificationStatus.SENT)}  # pushed by the training; no phone, so the inbox is the delivery

        async def first_days_match(session):
            first = set((await session.execute(
                select(Prediction.cell_id, func.min(Prediction.prediction_date)).group_by(Prediction.cell_id)
            )).all())
            notified = set((await session.execute(
                select(Prediction.cell_id, Prediction.prediction_date).join(Notification, Notification.prediction_id == Prediction.id)
            )).all())
            return first == notified

        assert db(client, first_days_match)

    def test_the_engineer_gets_one_email_with_the_dates_and_a_push_that_points_to_it(
        self, client, engineer_headers, supervisor_headers, fake_push, mails
    ):
        add_device(client, engineer_headers)
        force_limit(client, 1.0)
        fake_push.calls.clear()
        train(client, engineer_headers)
        [(_, subject, body)] = [m for m in mails if m[1].startswith("Pronósticos nuevos")]
        assert subject == "Pronósticos nuevos: celdas sobre el umbral de 1.00 V"
        assert "Con el pronóstico generado el" in body and "superaría el umbral de 1.00 V" in body
        assert "Te recomendamos tomar nota de las fechas y celdas mencionadas." in body
        assert "2 días y 1 día antes de cada fecha." in body
        assert body.count("<li>") >= 1
        assert {r.status for r in alerts(client, VOLTAGE_EXCEEDED, NotificationChannel.EMAIL)} == {NotificationStatus.SENT}
        assert len(alerts(client, VOLTAGE_EXCEEDED, NotificationChannel.EMAIL)) == CELLS  # still one row per cell
        assert [call[2] for call in fake_push.calls] == ["Se han recibido nuevos pronósticos, revisa tu correo electrónico."]

    def test_no_notification_when_nothing_exceeds_the_limit(self, client, engineer_headers, supervisor_headers):
        force_limit(client, 9.0)  # above any real voltage and outside the API range
        train(client, engineer_headers)
        assert alerts(client, VOLTAGE_EXCEEDED) == alerts(client, VOLTAGE_EXCEEDED, NotificationChannel.EMAIL) == []

    def test_no_notification_without_a_limit(self, client, engineer_headers):
        train(client, engineer_headers)
        assert alerts(client, VOLTAGE_EXCEEDED) == []

    def test_supervisors_are_not_notified(self, client, supervisor_headers, register_engineer):
        force_limit(client, 1.0)
        user_id, headers = register_engineer()
        train(client, headers)
        assert {r.user_id for r in alerts(client, VOLTAGE_EXCEEDED)} == {user_id}

    def test_a_new_version_replaces_the_alerts_of_the_previous_one(self, client, engineer_headers, supervisor_headers):
        force_limit(client, 1.0)
        dataset = cleaned_dataset(client, engineer_headers)
        request_training(client, engineer_headers, dataset)
        run_training(client)
        request_training(client, engineer_headers, dataset)
        run_training(client)

        async def models_of_the_alerts(session):
            return set((await session.execute(
                select(Prediction.model_id).join(Notification, Notification.prediction_id == Prediction.id)
            )).scalars())

        active = client.get(f"{API}/forecasts", headers=engineer_headers).json()["model"]["id"]
        assert len(alerts(client, VOLTAGE_EXCEEDED)) == CELLS  # not 2 x CELLS
        assert db(client, models_of_the_alerts) == {active}


class TestDateNear:  # US028
    NOW = datetime(2030, 1, 1, 8, 0)

    def prepare(self, client, headers, supervisor_headers):
        """A trained model whose first two forecasts are tomorrow and the day after, both above the limit."""
        train(client, headers)
        force_limit(client, 1.0)

        async def move(session):
            ids = (await session.execute(select(Prediction.id).order_by(Prediction.id).limit(2))).scalars().all()
            await session.execute(update(Prediction).where(Prediction.id == ids[0]).values(prediction_date=datetime(2030, 1, 2)))
            await session.execute(update(Prediction).where(Prediction.id == ids[1]).values(prediction_date=datetime(2030, 1, 3)))
            await session.commit()
            return ids

        return db(client, move)

    def remind(self, client):
        async def run(session):
            await remind_near_exceedances(session, self.NOW)

        db(client, run)

    def test_reminds_two_days_and_one_day_before_the_forecast_date(self, client, engineer_headers, supervisor_headers):
        ids = self.prepare(client, engineer_headers, supervisor_headers)
        self.remind(client)
        assert [r.prediction_id for r in alerts(client, DATE_NEAR)] == [ids[0]]  # tomorrow
        assert [r.prediction_id for r in alerts(client, DATE_NEAR_2_DAYS)] == [ids[1]]  # the day after tomorrow

    def test_each_reminder_goes_by_email_and_push_naming_the_cells_and_the_date(
        self, client, engineer_headers, supervisor_headers, fake_push, mails
    ):
        add_device(client, engineer_headers)
        self.prepare(client, engineer_headers, supervisor_headers)
        fake_push.calls.clear()
        mails.clear()
        self.remind(client)

        async def dispatch(session):
            await notifier_for(session).dispatch_pending()

        db(client, dispatch)
        pushes = {title: body for _, title, body in fake_push.calls}
        assert pushes["Revisa la celda: voltaje excesivo próximo"].startswith("Para el 02/01/2030 la celda ")
        assert pushes["Revisa la celda: voltaje excesivo en 2 días"].startswith("Para el 03/01/2030 la celda ")
        assert all(body.endswith("superará el umbral de 1.00 V") for body in pushes.values())
        emails = {subject: body for _, subject, body in mails}
        assert "<b>02/01/2030</b>" in emails["Revisa la celda: voltaje excesivo próximo"]
        assert "<b>03/01/2030</b>" in emails["Revisa la celda: voltaje excesivo en 2 días"]

    def test_reminds_once_per_notice(self, client, engineer_headers, supervisor_headers):
        self.prepare(client, engineer_headers, supervisor_headers)
        self.remind(client)
        self.remind(client)
        assert len(alerts(client, DATE_NEAR)) == 1
        assert len(alerts(client, DATE_NEAR_2_DAYS)) == 1

    def test_does_not_remind_of_forecasts_within_the_limit(self, client, engineer_headers, supervisor_headers):
        self.prepare(client, engineer_headers, supervisor_headers)
        force_limit(client, 9.0)
        self.remind(client)
        assert alerts(client, DATE_NEAR) == alerts(client, DATE_NEAR_2_DAYS) == []

    def test_a_new_version_clears_the_reminders_of_the_previous_one(self, client, engineer_headers, supervisor_headers):
        self.prepare(client, engineer_headers, supervisor_headers)
        self.remind(client)
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        assert alerts(client, DATE_NEAR) == alerts(client, DATE_NEAR_2_DAYS) == []
