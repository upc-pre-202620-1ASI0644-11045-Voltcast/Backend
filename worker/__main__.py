"""Usage: python -m worker etl"""
import argparse
import asyncio
import logging

from shared.infrastructure.persistence.configuration.database_configuration import close_db
from worker.main import TASKS, run


async def main(task: str) -> None:
    try:
        await run(task)
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runs one execution of a heavy task")
    parser.add_argument("task", choices=sorted(TASKS))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main(parser.parse_args().task))
