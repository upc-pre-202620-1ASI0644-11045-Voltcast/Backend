from notification_management.interface.notifier import notifier_for
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from worker.tasks.voltage_alerts import remind_near_exceedances


async def process_notifications() -> None:
    """
    One run of the scheduled Job (every few minutes): queues the reminders of the forecasts that are one day or less
    away (US028) and sends the emails that are still pending (US029, US030). Both are safe to repeat.
    """
    async with AsyncSessionLocal() as session:
        await remind_near_exceedances(session)
        await notifier_for(session).dispatch_pending()
