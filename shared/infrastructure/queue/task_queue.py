import logging

logger = logging.getLogger(__name__)

# Azure Storage Queue names: lowercase letters, numbers and hyphens only.
ETL_QUEUE = "etl-tasks"
TRAINING_QUEUE = "training-tasks"


class InMemoryTaskQueue:
    """
    Keeps the messages in memory so the API can be developed and tested without Azure.
    shortcut: the messages are lost when the process restarts and no Job consumes them; the Azure Storage Queue
    implementation replaces it in the cloud setup.
    """

    def __init__(self):
        self.messages: list[tuple[str, dict]] = []

    async def send(self, queue: str, message: dict) -> None:
        self.messages.append((queue, message))
        logger.info("Task queued in memory: %s %s", queue, message)


_queue = InMemoryTaskQueue()


def get_task_queue() -> InMemoryTaskQueue:
    return _queue
