import os
from pathlib import Path

import pandas as pd

from shared.infrastructure.queue.task_queue import ETL_QUEUE, TRAINING_QUEUE, get_task_queue
from tests.api.test_cells import CELLS, create_cell
from tests.api.test_datasets import DATASETS, upload
from tests.conftest import API
from tests.excel_files import section_rows, workbook_bytes
from worker.main import run

TWO_SECTIONS = {"EL A 2020_2026": section_rows(cells=[1, 2, 3]), "EL_B": section_rows(cells=[1, 2])}


def run_etl(client) -> bool:
    """One execution of the ETL Job over the next queued message."""
    return client.portal.call(run, "etl")


def uploaded(client, headers, sheets=None, content=None) -> int:
    response = upload(client, headers, content=content or workbook_bytes(sheets or TWO_SECTIONS))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def dataset(client, headers, dataset_id) -> dict:
    return client.get(f"{DATASETS}/{dataset_id}", headers=headers).json()


class TestCleanDataset:  # US001-US004
    def test_cleans_the_file_and_leaves_the_dataset_ready(self, client, engineer_headers):
        dataset_id = uploaded(client, engineer_headers)
        assert run_etl(client) is True
        body = dataset(client, engineer_headers, dataset_id)
        assert body["upload_status"] == "ready" and body["error_message"] is None
        assert (body["row_count"], body["processed_row_count"]) == (60, 150)  # 2 x 30 days; 5 cells x 30 days
        assert get_task_queue().pending(ETL_QUEUE) == []
        silver = pd.read_parquet(Path(os.environ["LOCAL_STORAGE_DIR"]) / "processed" / str(dataset_id) / "voltajes_silver.parquet")
        assert len(silver) == 150 and silver["celda"].nunique() == 5

    def test_reports_how_many_cells_were_found(self, client, engineer_headers):  # US003-E01
        dataset_id = uploaded(client, engineer_headers)
        run_etl(client)
        summary = dataset(client, engineer_headers, dataset_id)["summary"]
        assert summary["sections"] == {"A": 3, "B": 2} and summary["n_cells"] == 5
        assert (summary["date_from"], summary["date_to"], summary["new_cells"]) == ("2026-01-01", "2026-01-30", 5)

    def test_reports_the_cleaning_counts(self, client, engineer_headers):  # US004, TS008
        dataset_id = uploaded(client, engineer_headers)
        run_etl(client)
        summary = dataset(client, engineer_headers, dataset_id)["summary"]
        assert {k: summary[k] for k in ("rows_read", "rows_sorted", "duplicates_removed", "discarded_rows")} == {
            "rows_read": 60, "rows_sorted": 60, "duplicates_removed": 0, "discarded_rows": 0}

    def test_registers_the_cells_that_do_not_exist_yet(self, client, engineer_headers):
        existing = create_cell(client, engineer_headers, "A1")
        uploaded(client, engineer_headers)
        run_etl(client)
        cells = client.get(CELLS, headers=engineer_headers).json()
        assert sorted(c["name"] for c in cells) == ["A1", "A2", "A3", "B1", "B2"]
        assert {c["id"] for c in cells if c["name"] == "A1"} == {existing["id"]}  # reused, not duplicated
        assert not any(c["is_active"] for c in cells)  # active only with a cathode and an anode

    def test_a_cleaned_dataset_is_queued_for_training_by_itself(self, client, engineer_headers):
        dataset_id = uploaded(client, engineer_headers)
        run_etl(client)
        runs = client.get(f"{API}/trainings", headers=engineer_headers).json()
        assert [(r["dataset_id"], r["status"], r["executed_by"]) for r in runs] == [(dataset_id, "running", None)]
        assert get_task_queue().pending(TRAINING_QUEUE) == [{"task": "training", "training_execution_id": runs[0]["id"]}]


class TestRejectDataset:  # US002-E02, US003-E02
    def test_a_file_without_date_column_fails_with_the_cause(self, client, engineer_headers):
        rows = section_rows()
        rows[0][0] = "Fecha"
        dataset_id = uploaded(client, engineer_headers, {"EL A": rows})
        assert run_etl(client) is True
        body = dataset(client, engineer_headers, dataset_id)
        assert body["upload_status"] == "failed" and "date column" in body["error_message"]
        assert get_task_queue().pending(ETL_QUEUE) == []
        assert client.get(CELLS, headers=engineer_headers).json() == []

    def test_a_file_without_cells_says_none_were_found(self, client, engineer_headers):
        dataset_id = uploaded(client, engineer_headers, {"EL A": [row[:3] for row in section_rows()]})
        run_etl(client)
        assert "No electrical cells were found" in dataset(client, engineer_headers, dataset_id)["error_message"]

    def test_a_workbook_without_section_sheets_fails(self, client, engineer_headers):
        dataset_id = uploaded(client, engineer_headers, {"Hoja1": section_rows()})
        run_etl(client)
        assert "No sheet identifies an electrical section" in dataset(client, engineer_headers, dataset_id)["error_message"]

    def test_a_file_that_is_not_a_workbook_fails(self, client, engineer_headers):
        dataset_id = uploaded(client, engineer_headers, content=b"this is not an excel file")
        run_etl(client)
        body = dataset(client, engineer_headers, dataset_id)
        assert body["upload_status"] == "failed" and "not a valid Excel workbook" in body["error_message"]

    def test_a_failed_dataset_cannot_be_used_to_train(self, client, engineer_headers):
        dataset_id = uploaded(client, engineer_headers, {"Hoja1": section_rows()})
        run_etl(client)
        assert client.post(f"{API}/trainings", headers=engineer_headers, json={"dataset_id": dataset_id}).status_code == 400


class TestWorkerRun:
    def test_does_nothing_when_the_queue_is_empty(self, client):
        assert run_etl(client) is False

    def test_drops_a_message_of_an_unknown_dataset(self, client):
        client.portal.call(get_task_queue().send, ETL_QUEUE, {"task": "etl", "dataset_id": 999})
        assert run_etl(client) is True
        assert get_task_queue().pending(ETL_QUEUE) == []

    def test_handles_one_message_per_run_in_arrival_order(self, client, engineer_headers):
        first, second = (uploaded(client, engineer_headers) for _ in range(2))
        run_etl(client)
        assert dataset(client, engineer_headers, first)["upload_status"] == "ready"
        assert dataset(client, engineer_headers, second)["upload_status"] == "raw"
        run_etl(client)
        assert dataset(client, engineer_headers, second)["upload_status"] == "ready"
