from datetime import datetime
from math import isclose

from dataset_management.domain.model.aggregates.UploadedDataset import DatasetStatus, UploadedDataset
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from shared.infrastructure.queue.task_queue import TRAINING_QUEUE, get_task_queue
from tests.api.test_cells import create_cell
from tests.conftest import API
from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution, TrainingStatus

FORECASTS = f"{API}/forecasts"
TRAININGS = f"{API}/trainings"
ALERT_RULES = f"{API}/alert-rules"


def seed(client, *rows):
    """Inserts rows the Job would write; returns their ids in order."""

    async def run():
        async with AsyncSessionLocal() as session:
            session.add_all(rows)
            await session.commit()
            return [row.id for row in rows]

    return client.portal.call(run)


def active_model(client) -> int:
    return seed(client, MlModel(name="bi_lstm", version="v1", artifact_path="models/bi_lstm/v1", is_active=True))[0]


def forecast(model_id, cell_id, day, voltage):
    return Prediction(model_id=model_id, cell_id=cell_id, prediction_date=datetime(2026, 9, day), predicted_voltage=voltage)


def ready_dataset(client) -> int:
    return seed(client, UploadedDataset(filename="v.xlsx", storage_path="raw/x.xlsx", upload_status=DatasetStatus.READY))[0]


class TestViewForecasts:  # US007, US008
    def test_without_a_trained_model_says_there_is_nothing_yet(self, client, engineer_headers):
        body = client.get(FORECASTS, headers=engineer_headers).json()
        assert body["model"] is None and body["items"] == [] and "No trained model" in body["message"]

    def test_shows_the_first_day_of_every_cell_by_default(self, client, engineer_headers):
        a1, b1 = (create_cell(client, engineer_headers, n)["id"] for n in ("A1", "B1"))
        model = active_model(client)
        seed(client, forecast(model, a1, 1, 2.9), forecast(model, b1, 1, 3.0), forecast(model, a1, 2, 3.1))
        body = client.get(FORECASTS, headers=engineer_headers).json()
        assert [(i["cell_name"], i["date"]) for i in body["items"]] == [("A1", "2026-09-01"), ("B1", "2026-09-01")]
        assert (body["available_from"], body["available_to"]) == ("2026-09-01", "2026-09-02")
        assert body["model"]["version"] == "v1" and body["retraining"] is False

    def test_filters_by_date_range_and_cell(self, client, engineer_headers):
        a1, b1 = (create_cell(client, engineer_headers, n)["id"] for n in ("A1", "B1"))
        model = active_model(client)
        seed(client, *[forecast(model, c, d, 3.0) for c in (a1, b1) for d in (1, 2, 3)])
        one_day = client.get(FORECASTS, headers=engineer_headers, params={"date_from": "2026-09-02"}).json()
        assert {i["date"] for i in one_day["items"]} == {"2026-09-02"} and len(one_day["items"]) == 2
        span = client.get(FORECASTS, headers=engineer_headers,
                          params={"date_from": "2026-09-02", "date_to": "2026-09-03", "cell_id": b1}).json()
        assert [(i["cell_name"], i["date"]) for i in span["items"]] == [("B1", "2026-09-02"), ("B1", "2026-09-03")]

    def test_a_date_without_forecasts_returns_no_items(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)["id"]
        seed(client, forecast(active_model(client), cell, 1, 3.0))
        body = client.get(FORECASTS, headers=engineer_headers, params={"date_from": "2026-12-01"}).json()
        assert body["items"] == []

    def test_rejects_an_end_date_before_the_start(self, client, engineer_headers):
        seed(client, forecast(active_model(client), create_cell(client, engineer_headers)["id"], 1, 3.0))
        response = client.get(FORECASTS, headers=engineer_headers,
                              params={"date_from": "2026-09-03", "date_to": "2026-09-01"})
        assert response.status_code == 400

    def test_flags_the_cells_above_the_allowed_voltage(self, client, engineer_headers, supervisor_headers):
        a1, b1 = (create_cell(client, engineer_headers, n)["id"] for n in ("A1", "B1"))
        model = active_model(client)
        seed(client, forecast(model, a1, 1, 3.4), forecast(model, b1, 1, 3.4))
        assert client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": 3.36}).status_code == 201
        # B1 gets its own, looser limit: only A1 exceeds.
        assert client.post(ALERT_RULES, headers=supervisor_headers,
                           json={"max_voltage": 3.45, "cell_id": b1}).status_code == 201
        items = client.get(FORECASTS, headers=engineer_headers).json()["items"]
        assert [(i["cell_name"], i["max_voltage"], i["exceeds"]) for i in items] == [("A1", 3.36, True), ("B1", 3.45, False)]

    def test_the_exceeds_filter_keeps_only_the_cells_above_or_within_the_limit(self, client, engineer_headers, supervisor_headers):
        a1, b1, c1 = (create_cell(client, engineer_headers, n)["id"] for n in ("A1", "B1", "C1"))
        model = active_model(client)
        seed(client, forecast(model, a1, 1, 3.4), forecast(model, b1, 1, 3.1), forecast(model, c1, 1, 3.44),
             forecast(model, a1, 2, 3.0), forecast(model, b1, 2, 3.5))
        client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": 3.36})
        both_days = {"date_from": "2026-09-01", "date_to": "2026-09-02"}

        def names(**params):
            items = client.get(FORECASTS, headers=engineer_headers, params={**both_days, **params}).json()["items"]
            return [(i["cell_name"], i["date"]) for i in items]

        assert names(exceeds="true") == [("A1", "2026-09-01"), ("C1", "2026-09-01"), ("B1", "2026-09-02")]
        assert names(exceeds="false") == [("B1", "2026-09-01"), ("A1", "2026-09-02")]
        assert len(names()) == 5
        assert names(exceeds="true", cell_id=a1) == [("A1", "2026-09-01")]
        assert names(exceeds="true", date_from="2026-09-02", date_to="2026-09-02") == [("B1", "2026-09-02")]

    def test_the_exceeds_filter_returns_nothing_when_no_limit_is_set(self, client, engineer_headers):
        seed(client, forecast(active_model(client), create_cell(client, engineer_headers)["id"], 1, 99.0))
        assert client.get(FORECASTS, headers=engineer_headers, params={"exceeds": "true"}).json()["items"] == []
        assert len(client.get(FORECASTS, headers=engineer_headers, params={"exceeds": "false"}).json()["items"]) == 1

    def test_rejects_an_exceeds_value_that_is_not_a_boolean(self, client, engineer_headers):
        assert client.get(FORECASTS, headers=engineer_headers, params={"exceeds": "maybe"}).status_code == 422

    def test_without_a_limit_nothing_is_flagged(self, client, engineer_headers):
        seed(client, forecast(active_model(client), create_cell(client, engineer_headers)["id"], 1, 99.0))
        item = client.get(FORECASTS, headers=engineer_headers).json()["items"][0]
        assert (item["max_voltage"], item["exceeds"]) == (None, False)

    def test_hidden_cells_are_left_out(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)["id"]
        seed(client, forecast(active_model(client), cell, 1, 3.0))
        assert client.patch(f"{API}/cells/{cell}/hide", headers=engineer_headers).status_code == 200
        assert client.get(FORECASTS, headers=engineer_headers).json()["items"] == []

    def test_requires_authentication(self, client):
        assert client.get(FORECASTS).status_code in (401, 403)


class TestRetraining:  # US005-E02, US006-E02
    def test_warns_and_keeps_serving_the_latest_version(self, client, engineer_headers):
        cell = create_cell(client, engineer_headers)["id"]
        model = active_model(client)
        seed(client, forecast(model, cell, 1, 3.0))
        dataset = ready_dataset(client)
        seed(client, TrainingExecution(model_id=model, dataset_id=dataset))
        for url in (FORECASTS, f"{FORECASTS}/metrics"):
            body = client.get(url, headers=engineer_headers).json()
            assert body["retraining"] is True and "new version will be available soon" in body["message"], url
            assert body["model"]["version"] == "v1"
        assert len(client.get(FORECASTS, headers=engineer_headers).json()["items"]) == 1


class TestModelMetrics:  # US006
    def test_reports_the_accuracy_measured_when_the_active_model_was_trained(self, client, engineer_headers):
        model = active_model(client)
        dataset = ready_dataset(client)
        seed(client, TrainingExecution(model_id=model, dataset_id=dataset, status=TrainingStatus.SUCCESS,
                                       rmse=0.05, mae=0.02, mape=0.7, r2=0.8))
        body = client.get(f"{FORECASTS}/metrics", headers=engineer_headers).json()
        assert body["model"]["id"] == model and body["retraining"] is False
        assert isclose(body["mse"], 0.0025) and (body["rmse"], body["mae"], body["mape"], body["r2"]) == (0.05, 0.02, 0.7, 0.8)

    def test_without_a_finished_run_there_are_no_metrics(self, client, engineer_headers):
        active_model(client)
        body = client.get(f"{FORECASTS}/metrics", headers=engineer_headers).json()
        assert (body["mse"], body["rmse"], body["r2"]) == (None, None, None)

    def test_without_a_trained_model_says_there_is_nothing_yet(self, client, engineer_headers):
        body = client.get(f"{FORECASTS}/metrics", headers=engineer_headers).json()
        assert body["model"] is None and "No trained model" in body["message"]


class TestRequestTraining:  # US005
    def test_queues_a_new_model_version_on_a_ready_dataset(self, client, engineer_headers):
        dataset = ready_dataset(client)
        response = client.post(TRAININGS, headers=engineer_headers, json={"dataset_id": dataset})
        assert response.status_code == 202
        body = response.json()
        assert (body["status"], body["dataset_id"], body["finished_at"]) == ("running", dataset, None)
        assert get_task_queue().pending(TRAINING_QUEUE) == [{"task": "training", "training_execution_id": body["id"]}]
        assert client.get(f"{TRAININGS}/{body['id']}", headers=engineer_headers).json()["status"] == "running"
        # The new version is not served until the Job activates it.
        assert client.get(FORECASTS, headers=engineer_headers).json()["model"] is None

    def test_rejects_a_dataset_that_is_not_ready(self, client, engineer_headers):
        raw = seed(client, UploadedDataset(filename="v.xlsx", storage_path="raw/x.xlsx"))[0]
        response = client.post(TRAININGS, headers=engineer_headers, json={"dataset_id": raw})
        assert response.status_code == 400 and "not ready" in response.json()["detail"]

    def test_rejects_an_unknown_dataset(self, client, engineer_headers):
        assert client.post(TRAININGS, headers=engineer_headers, json={"dataset_id": 999}).status_code == 400

    def test_only_one_training_at_a_time(self, client, engineer_headers):
        dataset = ready_dataset(client)
        assert client.post(TRAININGS, headers=engineer_headers, json={"dataset_id": dataset}).status_code == 202
        response = client.post(TRAININGS, headers=engineer_headers, json={"dataset_id": dataset})
        assert response.status_code == 400 and "already in progress" in response.json()["detail"]

    def test_unknown_training_is_not_found(self, client, engineer_headers):
        assert client.get(f"{TRAININGS}/999", headers=engineer_headers).status_code == 404


class TestAlertRules:  # US007-E02
    def test_only_the_supervisor_sets_the_limit(self, client, engineer_headers):
        assert client.post(ALERT_RULES, headers=engineer_headers, json={"max_voltage": 3.4}).status_code == 403

    def test_a_new_limit_replaces_the_previous_one_of_its_scope(self, client, engineer_headers, supervisor_headers):
        for volts in (3.36, 3.4):
            assert client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": volts}).status_code == 201
        rules = client.get(ALERT_RULES, headers=engineer_headers).json()
        assert [(r["cell_id"], r["max_voltage"]) for r in rules] == [(None, 3.4)]

    def test_rejects_an_unknown_cell(self, client, supervisor_headers):
        assert client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": 3.4, "cell_id": 99}).status_code == 400

    def test_the_limit_must_be_above_3_35_and_at_most_3_45(self, client, supervisor_headers):
        def status(volts):
            return client.post(ALERT_RULES, headers=supervisor_headers, json={"max_voltage": volts}).status_code

        assert [status(v) for v in (0, 3.35, 3.451, 4)] == [422] * 4
        assert [status(v) for v in (3.351, 3.45)] == [201] * 2
