import logging

from shared.infrastructure.queue.task_queue import ETL_QUEUE, TRAINING_QUEUE, get_task_queue
from shared.infrastructure.storage.file_storage import get_file_storage
from worker.tasks.etl_task import process_etl
from worker.tasks.training_task import process_training

logger = logging.getLogger(__name__)

# task name -> (queue it reads, handler)
TASKS = {"etl": (ETL_QUEUE, process_etl), "training": (TRAINING_QUEUE, process_training)}


async def run(task: str) -> bool:
    """
    Handles one message of the task's queue, like one execution of a Container Apps Job started by KEDA.
    The message is deleted only after it was handled. Returns False when the queue was empty.
    """
    queue_name, handler = TASKS[task]
    queue = get_task_queue()
    received = await queue.receive(queue_name)
    if received is None:
        logger.info("No messages in %s", queue_name)
        return False
    message, handle = received
    await handler(message, get_file_storage())
    await queue.delete(handle)
    return True
