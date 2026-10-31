import os
from datetime import date, timedelta
from functools import partial
from pathlib import Path

import pytest
from sqlalchemy import func, select

from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from shared.infrastructure.queue.task_queue import TRAINING_QUEUE, get_task_queue
from tests.api.test_datasets import upload
from tests.api.test_etl import run_etl
from tests.conftest import API
from tests.excel_files import section_rows, varying_rows, workbook_bytes
from voltage_forecasting.domain.model.aggregates.ModelEvaluation import ModelEvaluationResult
from worker.main import run
from worker.training import config
from worker.training.pipeline import train

FORECASTS = f"{API}/forecasts"
TRAININGS = f"{API}/trainings"
ALERT_RULES = f"{API}/alert-rules"

# A tiny network so the tests train in seconds; the recipe itself is the PoC one.
SMALL = {**config.TRAIN, "hidden": 8, "head_hidden": 16, "max_epochs": 3, "patience": 2}


@pytest.fixture(autouse=True)
def small_network(monkeypatch):
    monkeypatch.setattr("worker.tasks.training_task.train", partial(train, cfg=SMALL, n_jobs=1))


def db(client, fn):
    async def run_query():
        async with AsyncSessionLocal() as session:
            return await fn(session)

    return client.portal.call(run_query)


def run_training(client) -> bool:
    return client.portal.call(run, "training")


DAYS = config.MIN_DAYS  # the least that can be validated
LAST_DAY = date(2020, 1, 1) + timedelta(days=DAYS - 1)  # the synthetic workbooks start on 2020-01-01


def cleaned_dataset(client, headers, days=DAYS) -> int:
    sheets = {"EL A 2020_2026": varying_rows(days, [1, 2, 3]), "Sección B": varying_rows(days, [1, 2], seed=1)}
    response = upload(client, headers, content=workbook_bytes(sheets))
    assert response.status_code == 201, response.text
    run_etl(client)
    return response.json()["id"]


def request_training(client, headers, dataset_id) -> dict:
    """The training the ETL queued on its own, or a new one when that one already ran."""
    queued = [t for t in client.get(TRAININGS, headers=headers).json() if t["dataset_id"] == dataset_id and t["status"] == "running"]
    if queued:
        return queued[0]
    response = client.post(TRAININGS, headers=headers, json={"dataset_id": dataset_id})
    assert response.status_code == 202, response.text
    return response.json()


class TestTrainModel:  # US005, US006
    def test_trains_forecasts_and_activates_the_new_version(self, client, engineer_headers):
        dataset = cleaned_dataset(client, engineer_headers)
        training = request_training(client, engineer_headers, dataset)
        assert run_training(client) is True

        done = client.get(f"{TRAININGS}/{training['id']}", headers=engineer_headers).json()
        assert done["status"] == "success" and done["finished_at"] is not None
        assert all(done[m] is not None for m in ("rmse", "mae", "mape", "r2"))
        assert get_task_queue().pending(TRAINING_QUEUE) == []

        body = client.get(FORECASTS, headers=engineer_headers).json()
        assert body["model"]["id"] == training["model_id"] and body["retraining"] is False
        assert (body["available_from"], body["available_to"]) == (
            str(LAST_DAY + timedelta(days=1)), str(LAST_DAY + timedelta(days=config.HORIZON_DAYS)))
        assert len(body["items"]) == 5  # one day of the 5 cells

    def test_forecasts_cover_the_whole_horizon_by_date(self, client, engineer_headers):
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        span = client.get(FORECASTS, headers=engineer_headers,
                          params={"date_from": str(LAST_DAY + timedelta(days=1)), "date_to": str(LAST_DAY + timedelta(days=180)), "cell_id": 1}).json()
        assert len(span["items"]) == 180 and {i["cell_name"] for i in span["items"]} == {"A1"}

    def test_the_metrics_are_the_ones_measured_on_the_validation_days(self, client, engineer_headers):
        training = request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        metrics = client.get(f"{FORECASTS}/metrics", headers=engineer_headers).json()
        done = client.get(f"{TRAININGS}/{training['id']}", headers=engineer_headers).json()
        assert (metrics["rmse"], metrics["mae"], metrics["mape"], metrics["r2"]) == (done["rmse"], done["mae"], done["mape"], done["r2"])
        assert metrics["rmse"] ** 2 == pytest.approx(metrics["mse"]) and 0 < metrics["mae"] <= metrics["rmse"]

    def test_stores_a_backtest_of_every_cell_against_the_measured_voltage(self, client, engineer_headers):
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)

        async def count(session):
            return (await session.execute(select(func.count(), func.count(func.distinct(ModelEvaluationResult.cell_id))))).one()

        assert db(client, count) == (5 * config.BACKTEST_DAYS, 5)

    def test_saves_the_model_files(self, client, engineer_headers):
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        folder = Path(os.environ["LOCAL_STORAGE_DIR"]) / "models" / "bi_lstm"
        assert {f.name for f in folder.glob("*/*")} == {"model.pt", "scalers.json"}

    def test_a_new_version_replaces_the_forecasts_of_the_previous_one(self, client, engineer_headers):
        dataset = cleaned_dataset(client, engineer_headers)
        first = request_training(client, engineer_headers, dataset)
        run_training(client)
        second = request_training(client, engineer_headers, dataset)
        run_training(client)
        body = client.get(FORECASTS, headers=engineer_headers).json()
        assert body["model"]["id"] == second["model_id"] != first["model_id"] and len(body["items"]) == 5
        # The previous run stays visible, only its forecasts are gone.
        assert client.get(f"{TRAININGS}/{first['id']}", headers=engineer_headers).json()["status"] == "success"
        assert len(client.get(TRAININGS, headers=engineer_headers).json()) == 2

    def test_flags_the_cells_forecast_above_the_allowed_voltage(self, client, engineer_headers, supervisor_headers):
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": 1.0})  # below any real voltage
        items = client.get(FORECASTS, headers=engineer_headers).json()["items"]
        assert items and all(i["exceeds"] for i in items)


class TestEvaluationTable:  # US006: forecast against measured voltage, cell by cell
    EVALUATION = f"{FORECASTS}/evaluation"

    def trained(self, client, headers):
        request_training(client, headers, cleaned_dataset(client, headers))
        run_training(client)

    def test_compares_every_cell_on_the_latest_day_of_the_backtest(self, client, engineer_headers):
        self.trained(client, engineer_headers)
        body = client.get(self.EVALUATION, headers=engineer_headers).json()
        assert (body["available_from"], body["available_to"]) == (
            str(LAST_DAY - timedelta(days=config.BACKTEST_DAYS - 1)), str(LAST_DAY))
        assert body["date"] == str(LAST_DAY) and body["total_cells"] == 5 and len(body["items"]) == 5
        for item in body["items"]:
            assert item["error_v"] == pytest.approx(abs(item["real"] - item["predicted"]))
            assert item["error_pct"] == pytest.approx(100 * item["error_v"] / item["real"])
        assert body["mean_error_pct"] == pytest.approx(sum(i["error_pct"] for i in body["items"]) / 5)

    def test_returns_the_cells_with_the_largest_error_first_or_the_smallest(self, client, engineer_headers):
        self.trained(client, engineer_headers)
        worst = client.get(self.EVALUATION, headers=engineer_headers, params={"limit": 3}).json()
        best = client.get(self.EVALUATION, headers=engineer_headers, params={"limit": 3, "order": "best"}).json()
        everything = [i["error_pct"] for i in client.get(self.EVALUATION, headers=engineer_headers, params={"limit": 300}).json()["items"]]
        assert [i["error_pct"] for i in worst["items"]] == sorted(everything, reverse=True)[:3]
        assert [i["error_pct"] for i in best["items"]] == sorted(everything)[:3]
        assert worst["total_cells"] == best["total_cells"] == 5 and worst["mean_error_pct"] == best["mean_error_pct"]

    def test_a_day_of_the_backtest_can_be_chosen(self, client, engineer_headers):
        self.trained(client, engineer_headers)
        day = str(LAST_DAY - timedelta(days=10))
        assert client.get(self.EVALUATION, headers=engineer_headers, params={"date": day}).json()["date"] == day

    def test_a_day_without_comparison_is_refused_with_the_available_range(self, client, engineer_headers):
        self.trained(client, engineer_headers)
        response = client.get(self.EVALUATION, headers=engineer_headers, params={"date": str(LAST_DAY + timedelta(days=1))})
        assert response.status_code == 400 and str(LAST_DAY) in response.json()["detail"]
        assert client.get(self.EVALUATION, headers=engineer_headers, params={"limit": 301}).status_code == 422
        assert client.get(self.EVALUATION, headers=engineer_headers, params={"order": "up"}).status_code == 422

    def test_says_so_when_there_is_no_trained_model(self, client, engineer_headers):
        body = client.get(self.EVALUATION, headers=engineer_headers).json()
        assert body["model"] is None and body["items"] == [] and body["message"]

    def test_the_series_has_a_point_per_day_equal_to_the_mean_error_of_that_day(self, client, engineer_headers):
        self.trained(client, engineer_headers)
        series = client.get(f"{self.EVALUATION}/series", headers=engineer_headers).json()
        assert len(series["items"]) == config.BACKTEST_DAYS
        assert (series["available_from"], series["available_to"]) == (series["items"][0]["date"], series["items"][-1]["date"])
        point = series["items"][10]
        assert point["total_cells"] == 5
        day = client.get(self.EVALUATION, headers=engineer_headers, params={"date": point["date"]}).json()
        assert point["mean_error_pct"] == pytest.approx(day["mean_error_pct"])

    def test_the_series_can_be_cut_and_refuses_days_outside_the_backtest(self, client, engineer_headers):
        self.trained(client, engineer_headers)
        first = str(LAST_DAY - timedelta(days=config.BACKTEST_DAYS - 1))
        cut = client.get(f"{self.EVALUATION}/series", headers=engineer_headers,
                         params={"date_from": first, "date_to": str(LAST_DAY - timedelta(days=config.BACKTEST_DAYS - 3))}).json()
        assert len(cut["items"]) == 3
        outside = {"date_to": str(LAST_DAY + timedelta(days=1))}
        assert client.get(f"{self.EVALUATION}/series", headers=engineer_headers, params=outside).status_code == 400
        backwards = {"date_from": str(LAST_DAY), "date_to": first}
        assert client.get(f"{self.EVALUATION}/series", headers=engineer_headers, params=backwards).status_code == 400

    def test_the_series_says_so_when_there_is_no_trained_model(self, client, engineer_headers):
        body = client.get(f"{self.EVALUATION}/series", headers=engineer_headers).json()
        assert body["model"] is None and body["items"] == [] and body["message"]


class TestTrainingThatCannotRun:
    def test_too_little_data_ends_as_failed_and_stays_visible(self, client, engineer_headers):
        training = request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers, days=60))
        assert run_training(client) is True
        failed = client.get(f"{TRAININGS}/{training['id']}", headers=engineer_headers).json()
        assert failed["status"] == "failed" and failed["finished_at"] is not None
        assert client.get(FORECASTS, headers=engineer_headers).json()["model"] is None
        # A failed run no longer blocks the next one.
        assert client.post(TRAININGS, headers=engineer_headers, json={"dataset_id": training["dataset_id"]}).status_code == 202

    def test_a_failed_run_keeps_the_previous_version_serving(self, client, engineer_headers):
        good = cleaned_dataset(client, engineer_headers)
        first = request_training(client, engineer_headers, good)
        run_training(client)
        short = upload(client, engineer_headers, content=workbook_bytes({"EL A": section_rows(days=60)})).json()["id"]
        run_etl(client)
        request_training(client, engineer_headers, short)
        run_training(client)
        body = client.get(FORECASTS, headers=engineer_headers).json()
        assert body["model"]["id"] == first["model_id"] and len(body["items"]) == 5 and body["retraining"] is False

    def test_does_nothing_when_the_queue_is_empty(self, client):
        assert run_training(client) is False

    def test_drops_a_message_of_an_unknown_training(self, client):
        client.portal.call(get_task_queue().send, TRAINING_QUEUE, {"task": "training", "training_execution_id": 999})
        assert run_training(client) is True
        assert get_task_queue().pending(TRAINING_QUEUE) == []
