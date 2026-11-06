from datetime import datetime

from sqlalchemy import func, select, update

from notification_management.domain.model.aggregates.Notification import (
    DATE_NEAR,
    VOLTAGE_EXCEEDED,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from tests.conftest import API
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


def alerts(client, code: str) -> list:
    async def read(session):
        rows = await session.execute(
            select(Notification).join(NotificationType).where(NotificationType.type == code).order_by(Notification.id)
        )
        return list(rows.scalars().unique())

    return db(client, read)


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

    def test_no_notification_when_nothing_exceeds_the_limit(self, client, engineer_headers, supervisor_headers):
        client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": 3.45})
        train(client, engineer_headers)
        assert alerts(client, VOLTAGE_EXCEEDED) == []

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

    def test_reminds_only_of_the_forecasts_one_day_or_less_away(self, client, engineer_headers, supervisor_headers):
        ids = self.prepare(client, engineer_headers, supervisor_headers)
        self.remind(client)
        assert [r.prediction_id for r in alerts(client, DATE_NEAR)] == [ids[0]]

    def test_reminds_once(self, client, engineer_headers, supervisor_headers):
        self.prepare(client, engineer_headers, supervisor_headers)
        self.remind(client)
        self.remind(client)
        assert len(alerts(client, DATE_NEAR)) == 1

    def test_does_not_remind_of_forecasts_within_the_limit(self, client, engineer_headers, supervisor_headers):
        self.prepare(client, engineer_headers, supervisor_headers)
        client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": 3.45})
        self.remind(client)
        assert alerts(client, DATE_NEAR) == []

    def test_a_new_version_clears_the_reminders_of_the_previous_one(self, client, engineer_headers, supervisor_headers):
        self.prepare(client, engineer_headers, supervisor_headers)
        self.remind(client)
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        assert alerts(client, DATE_NEAR) == []
