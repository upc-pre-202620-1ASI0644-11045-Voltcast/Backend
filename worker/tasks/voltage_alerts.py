from datetime import datetime, timedelta

from sqlalchemy import delete, func, insert, select

from iam.domain.model.aggregates.PasswordReset import utc_now_naive
from iam.domain.model.aggregates.Role import ROLE_USER, Role
from iam.domain.model.aggregates.User import User, UserStatus
from notification_management.domain.model.aggregates.Notification import (
    DATE_NEAR,
    DATE_NEAR_2_DAYS,
    VOLTAGE_EXCEEDED,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction


def _exceeding():
    """(id, cell_id) of the forecasts above their limit: the rule of the cell, else the general one, else none."""
    cell_rule = (
        select(AlertRule.cell_id, AlertRule.max_voltage)
        .where(AlertRule.is_active.is_(True), AlertRule.cell_id.is_not(None))
        .subquery()
    )
    general = (
        select(AlertRule.max_voltage)
        .where(AlertRule.is_active.is_(True), AlertRule.cell_id.is_(None))
        .limit(1)
        .scalar_subquery()
    )
    return (
        select(Prediction.id, Prediction.cell_id)
        .outerjoin(cell_rule, cell_rule.c.cell_id == Prediction.cell_id)
        .where(Prediction.predicted_voltage > func.coalesce(cell_rule.c.max_voltage, general))
    )


async def _type_ids(session, *codes: str) -> dict[str, int]:
    """Map notification type codes to their ids."""
    rows = await session.execute(select(NotificationType.type, NotificationType.id).where(NotificationType.type.in_(codes)))
    return dict(rows.all())


async def _queue(session, code: str, prediction_ids: list[int]) -> None:
    """One push and one email notification per active engineer and forecast; the ones already queued are left alone."""
    if not prediction_ids:
        return
    type_id = (await _type_ids(session, code))[code]
    engineers = (await session.execute(
        select(User.id).join(Role, User.role_id == Role.id).where(User.status == UserStatus.ACTIVE, Role.name == ROLE_USER)
    )).scalars().all()
    existing = set((await session.execute(
        select(Notification.user_id, Notification.prediction_id, Notification.channel).where(
            Notification.notification_type_id == type_id, Notification.prediction_id.in_(prediction_ids)
        )
    )).all())
    rows = [
        {"user_id": user_id, "prediction_id": prediction_id, "notification_type_id": type_id,
         "channel": channel, "status": NotificationStatus.PENDING}
        for user_id in engineers for prediction_id in prediction_ids
        for channel in (NotificationChannel.PUSH, NotificationChannel.EMAIL)
        if (user_id, prediction_id, channel) not in existing
    ]
    if rows:
        await session.execute(insert(Notification), rows)


def _today(now: datetime | None) -> datetime:
    """Return midnight of the given moment, or of today."""
    return (now or utc_now_naive()).replace(hour=0, minute=0, second=0, microsecond=0)


async def replace_voltage_alerts(session, model_id: int, now: datetime | None = None) -> None:
    """
    US026, inside the transaction that publishes a model: the alerts of the previous forecasts are gone with them, and
    every engineer is told, per cell, of the first day from today on that the new forecast goes above its limit (the
    first forecast days can already be past when the data reached the plant late). Does not commit.
    shortcut: days are cut at UTC midnight, not at the plant's local time; add a timezone setting if that matters.
    """
    old = await _type_ids(session, VOLTAGE_EXCEEDED, DATE_NEAR, DATE_NEAR_2_DAYS)
    await session.execute(delete(Notification).where(Notification.notification_type_id.in_(old.values())))
    first: dict[int, int] = {}
    for prediction_id, cell_id in await session.execute(
        _exceeding().where(Prediction.model_id == model_id, Prediction.prediction_date >= _today(now))
        .order_by(Prediction.prediction_date)
    ):
        first.setdefault(cell_id, prediction_id)
    await _queue(session, VOLTAGE_EXCEEDED, list(first.values()))


async def remind_near_exceedances(session, now: datetime | None = None) -> None:
    """
    US028: every engineer is reminded, once each, of every excess forecast when it is two days away and again when it is
    one day away (two separate notifications; a day the Job missed is not made up).
    shortcut: days are cut at UTC midnight, not at the plant's local time; add a timezone setting if that matters.
    """
    today = _today(now)
    for code, days in ((DATE_NEAR_2_DAYS, 2), (DATE_NEAR, 1)):
        day = today + timedelta(days=days)
        ids = (await session.execute(
            _exceeding().where(Prediction.prediction_date >= day, Prediction.prediction_date < day + timedelta(days=1))
        )).scalars().all()
        await _queue(session, code, list(ids))
    await session.commit()
