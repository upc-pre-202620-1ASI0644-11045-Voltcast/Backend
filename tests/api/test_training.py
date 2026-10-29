import os
from functools import partial
from pathlib import Path

import pytest

from shared.infrastructure.queue.task_queue import TRAINING_QUEUE, get_task_queue
from tests.api.test_datasets import upload
from tests.api.test_etl import run_etl
from tests.conftest import API
from tests.excel_files import section_rows, varying_rows, workbook_bytes
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


def run_training(client) -> bool:
    return client.portal.call(run, "training")


def cleaned_dataset(client, headers, days=520) -> int:
    sheets = {"EL A 2020_2026": varying_rows(days, [1, 2, 3]), "Sección B": varying_rows(days, [1, 2], seed=1)}
    response = upload(client, headers, content=workbook_bytes(sheets))
    assert response.status_code == 201, response.text
    run_etl(client)
    return response.json()["id"]


def request_training(client, headers, dataset_id) -> dict:
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
        assert (body["available_from"], body["available_to"]) == ("2026-06-05", "2026-12-01")  # 180 days after the data
        assert len(body["items"]) == 5  # one day of the 5 cells

    def test_forecasts_cover_the_whole_horizon_by_date(self, client, engineer_headers):
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        span = client.get(FORECASTS, headers=engineer_headers,
                          params={"date_from": "2026-06-05", "date_to": "2026-12-01", "cell_id": 1}).json()
        assert len(span["items"]) == 180 and {i["cell_name"] for i in span["items"]} == {"A1"}

    def test_the_metrics_compare_the_forecast_with_the_measured_voltage(self, client, engineer_headers):
        request_training(client, engineer_headers, cleaned_dataset(client, engineer_headers))
        run_training(client)
        metrics = client.get(f"{FORECASTS}/metrics", headers=engineer_headers).json()
        assert metrics["samples"] == 5 * config.BACKTEST_DAYS
        assert metrics["rmse"] ** 2 == pytest.approx(metrics["mse"])
        assert 0 < metrics["mae"] <= metrics["rmse"] and metrics["mape"] > 0

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
