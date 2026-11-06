import os
from pathlib import Path

from shared.infrastructure.queue.task_queue import ETL_QUEUE, get_task_queue
from tests.conftest import API

DATASETS = f"{API}/datasets"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload(client, headers, name="voltages.xlsx", content=b"excel-bytes"):
    return client.post(DATASETS, headers=headers, files={"file": (name, content, XLSX)})


class TestUploadDataset:  # US001
    def test_stores_the_file_and_queues_its_cleaning(self, client, engineer_headers):
        response = upload(client, engineer_headers)
        assert response.status_code == 201
        body = response.json()
        assert (body["filename"], body["upload_status"], body["row_count"]) == ("voltages.xlsx", "raw", 0)
        assert get_task_queue().pending(ETL_QUEUE) == [{"task": "etl", "dataset_id": body["id"]}]
        stored = list((Path(os.environ["LOCAL_STORAGE_DIR"]) / "raw").glob("*.xlsx"))
        assert [f.read_bytes() for f in stored] == [b"excel-bytes"]

    def test_rejects_an_unsupported_extension_with_the_cause(self, client, engineer_headers):
        for name in ("voltages.pdf", "voltages.csv", "voltages"):
            response = upload(client, engineer_headers, name)
            assert response.status_code == 400, name
            assert "Unsupported file format" in response.json()["detail"]
        assert get_task_queue().pending(ETL_QUEUE) == []

    def test_accepts_xls_and_stores_it_with_its_extension(self, client, engineer_headers):
        assert upload(client, engineer_headers, "voltages.XLS").status_code == 201
        assert len(list((Path(os.environ["LOCAL_STORAGE_DIR"]) / "raw").glob("*.xls"))) == 1

    def test_rejects_the_upload_while_a_training_is_in_progress(self, client, engineer_headers):
        from tests.api.test_etl import run_etl, uploaded

        uploaded(client, engineer_headers)
        run_etl(client)  # the ETL queues the training of the cleaned file, which is now in progress
        response = upload(client, engineer_headers)
        assert response.status_code == 400 and "training is in progress" in response.json()["detail"]
        assert get_task_queue().pending(ETL_QUEUE) == []

    def test_rejects_an_empty_file(self, client, engineer_headers):
        response = upload(client, engineer_headers, content=b"")
        assert response.status_code == 400 and "empty" in response.json()["detail"]

    def test_keeps_only_the_file_name_without_folders(self, client, engineer_headers):
        assert upload(client, engineer_headers, "..\\..\\secret\\voltages.XLSX").json()["filename"] == "voltages.XLSX"

    def test_requires_authentication(self, client):
        assert client.post(DATASETS, files={"file": ("a.xlsx", b"x", XLSX)}).status_code in (401, 403)


class TestReadDatasets:
    def test_follows_the_status_of_an_upload(self, client, engineer_headers):
        dataset_id = upload(client, engineer_headers).json()["id"]
        response = client.get(f"{DATASETS}/{dataset_id}", headers=engineer_headers)
        assert response.status_code == 200 and response.json()["upload_status"] == "raw"
        assert [d["id"] for d in client.get(DATASETS, headers=engineer_headers).json()] == [dataset_id]

    def test_unknown_dataset_is_not_found(self, client, engineer_headers):
        assert client.get(f"{DATASETS}/999", headers=engineer_headers).status_code == 404
