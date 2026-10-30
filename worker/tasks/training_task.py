import asyncio
import json
import logging
from io import BytesIO

import pandas as pd
from sqlalchemy import delete, insert, select, update

from cell_management.domain.model.aggregates.Cell import Cell
from dataset_management.infrastructure.persistence.repositories.DatasetRepositoryImpl import DatasetRepositoryImpl
from iam.domain.model.aggregates.User import User  # noqa: F401  the table `executed_by` points to must be known
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.ModelEvaluation import ModelEvaluation, ModelEvaluationResult
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution, TrainingStatus
from voltage_forecasting.infrastructure.persistence.repositories.TrainingRepositoryImpl import TrainingRepositoryImpl
from worker.etl.cleaning import database_cell_name
from worker.training.gold import TrainingDataError
from worker.training.pipeline import TrainingResult, train

logger = logging.getLogger(__name__)

CHUNK = 5000


async def _insert_all(session, table, rows: list[dict]) -> None:
    for i in range(0, len(rows), CHUNK):
        await session.execute(insert(table), rows[i:i + CHUNK])


async def _publish(session, storage, execution: TrainingExecution, model: MlModel, result: TrainingResult) -> None:
    """
    Saves the model files, then in a single transaction replaces the forecasts and evaluation rows of the previous
    versions by the new ones, makes this version the active one and closes the run. Until the commit the previous
    version keeps serving, and a failure leaves it untouched. Rows of the models and runs themselves are kept.
    """
    await storage.save(f"{model.artifact_path}/model.pt", result.checkpoint)
    await storage.save(f"{model.artifact_path}/scalers.json", json.dumps(result.scalers).encode())

    cell_ids = dict((await session.execute(select(Cell.name, Cell.id))).all())
    ids = result.predictions["celda"].map(lambda c: cell_ids.get(database_cell_name(c)))
    predictions = result.predictions.assign(cell_id=ids).dropna(subset=["cell_id"])
    ids = result.evaluation["celda"].map(lambda c: cell_ids.get(database_cell_name(c)))
    evaluation = result.evaluation.assign(cell_id=ids).dropna(subset=["cell_id"])

    previous = select(ModelEvaluation.id).where(ModelEvaluation.model_id != model.id)
    await session.execute(delete(ModelEvaluationResult).where(ModelEvaluationResult.model_evaluation_id.in_(previous)))
    await session.execute(delete(Prediction).where(Prediction.model_id != model.id))
    await session.execute(update(MlModel).where(MlModel.id != model.id).values(is_active=False))

    run = ModelEvaluation(model_id=model.id, dataset_id=execution.dataset_id)
    session.add(run)
    await session.flush()
    await _insert_all(session, ModelEvaluationResult, [
        {"model_evaluation_id": run.id, "cell_id": int(c), "prediction_date": d.to_pydatetime(),
         "predicted_value": float(p), "real_value": float(r)}
        for c, d, p, r in zip(evaluation["cell_id"], evaluation["fecha"], evaluation["predicho"], evaluation["real"])
    ])
    await _insert_all(session, Prediction, [
        {"model_id": model.id, "cell_id": int(c), "prediction_date": d.to_pydatetime(), "predicted_voltage": float(v)}
        for c, d, v in zip(predictions["cell_id"], predictions["fecha"], predictions["voltaje"])
    ])

    model.is_active = True
    execution.status = TrainingStatus.SUCCESS
    execution.rmse, execution.mae = result.metrics["rmse"], result.metrics["mae"]
    execution.mape, execution.r2 = result.metrics["mape"], result.metrics["r2"]
    execution.finished_at = pd.Timestamp.now("UTC").tz_localize(None).to_pydatetime()
    await session.commit()


async def process_training(message: dict, storage) -> None:
    """
    Trains a model version on a cleaned dataset, forecasts every cell and evaluates it (US005, US006).
    A dataset that cannot train a model ends the run as `failed` and keeps its row visible in the API; the cause
    goes to the log. An infrastructure error propagates, so the message stays in the queue and is retried.
    """
    execution_id = message["training_execution_id"]
    async with AsyncSessionLocal() as session:
        repository = TrainingRepositoryImpl(session)
        execution = await repository.find_by_id(execution_id)
        if execution is None or execution.status != TrainingStatus.RUNNING:
            logger.warning("Training %s is missing or already handled; message dropped", execution_id)
            return
        dataset = await DatasetRepositoryImpl(session).find_by_id(execution.dataset_id)
        model = await session.get(MlModel, execution.model_id)
        try:
            silver = pd.read_parquet(BytesIO(await storage.read(dataset.processed_path)), engine="pyarrow")
            result = await asyncio.to_thread(train, silver)
            await _publish(session, storage, execution, model, result)
            logger.info("Training %s done: model %s %s, %s", execution_id, model.name, model.version, result.metrics)
        except TrainingDataError as error:
            await session.rollback()
            logger.info("Training %s rejected: %s", execution_id, error)
            execution.mark_failed()
            await repository.save(execution)
        except Exception:
            await session.rollback()
            logger.exception("Training %s failed with an unexpected error", execution_id)
            execution.mark_failed()
            await repository.save(execution)
