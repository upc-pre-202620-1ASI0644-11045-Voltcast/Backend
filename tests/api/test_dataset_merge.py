from datetime import datetime

from shared.infrastructure.queue.task_queue import ETL_QUEUE, get_task_queue
from tests.api.test_datasets import DATASETS, XLSX
from tests.api.test_etl import dataset, run_etl, uploaded
from tests.conftest import API
from tests.excel_files import section_rows, workbook_bytes

BASE = {"EL A": section_rows(days=30, cells=[1, 2]), "EL B": section_rows(days=30, cells=[1])}  # 2026-01-01 .. 2026-01-30


def following(days=30, after_gap=5, cells=None, start=None):
    """The same sections, starting `after_gap` days after the base ends."""
    from datetime import timedelta

    start = start or datetime(2026, 1, 30) + timedelta(days=after_gap + 1)
    return {"EL A": section_rows(days=days, cells=cells or [1, 2], start=start), "EL B": section_rows(days=days, cells=[1], start=start)}


def upload_over(client, headers, base_id, sheets):
    return client.post(DATASETS, headers=headers, data={"base_dataset_id": base_id},
                       files={"file": ("new.xlsx", workbook_bytes(sheets), XLSX)})


def ready_base(client, headers) -> int:
    base_id = uploaded(client, headers, BASE)
    run_etl(client)
    assert dataset(client, headers, base_id)["upload_status"] == "ready"
    client.portal.call(finish_training, client)
    return base_id


async def finish_training(client):
    """The ETL queued a training on its own; it counts as done so uploads are accepted again."""
    from sqlalchemy import update

    from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
    from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution, TrainingStatus

    async with AsyncSessionLocal() as session:
        await session.execute(update(TrainingExecution).values(status=TrainingStatus.FAILED))
        await session.commit()


class TestAskBeforeMerging:
    def test_waits_for_the_user_with_what_the_merge_would_do(self, client, engineer_headers):
        base_id = ready_base(client, engineer_headers)
        response = upload_over(client, engineer_headers, base_id, following())
        assert response.status_code == 201 and response.json()["base_dataset_id"] == base_id
        run_etl(client)
        waiting = dataset(client, engineer_headers, response.json()["id"])
        assert waiting["upload_status"] == "awaiting_confirmation"
        assert waiting["summary"] == {
            "base": {"date_from": "2026-01-01", "date_to": "2026-01-30"},
            "new": {"date_from": "2026-02-05", "date_to": "2026-03-06"},
            "gap_days": 5, "overlap_days": 0, "merged_days": 65, "base_dataset_id": base_id,
        }

    def test_the_base_has_to_exist_and_be_ready(self, client, engineer_headers):
        raw = uploaded(client, engineer_headers, BASE)
        for base_id in (999, raw):
            response = upload_over(client, engineer_headers, base_id, following())
            assert response.status_code == 400 and "not ready" in response.json()["detail"]

    def test_confirming_merges_the_raw_data_and_leaves_the_dataset_ready(self, client, engineer_headers):
        base_id = ready_base(client, engineer_headers)
        new_id = upload_over(client, engineer_headers, base_id, following()).json()["id"]
        run_etl(client)
        assert client.post(f"{DATASETS}/{new_id}/confirm", headers=engineer_headers).status_code == 202
        run_etl(client)
        merged = dataset(client, engineer_headers, new_id)
        assert merged["upload_status"] == "ready"
        assert (merged["summary"]["date_from"], merged["summary"]["date_to"], merged["summary"]["days"]) == ("2026-01-01", "2026-03-06", 65)
        assert merged["row_count"] == 2 * 30 * 2  # both files, both sections
        # A cleaned dataset is trained on right away.
        runs = client.get(f"{API}/trainings", headers=engineer_headers).json()
        assert [r["dataset_id"] for r in runs if r["status"] == "running"] == [new_id]

    def test_the_new_file_wins_where_the_two_overlap(self, client, engineer_headers):
        base_id = ready_base(client, engineer_headers)
        new_id = upload_over(client, engineer_headers, base_id, following(after_gap=-10)).json()["id"]  # starts 10 days before the base ends
        run_etl(client)
        assert dataset(client, engineer_headers, new_id)["summary"]["overlap_days"] == 10
        client.post(f"{DATASETS}/{new_id}/confirm", headers=engineer_headers)
        run_etl(client)
        assert dataset(client, engineer_headers, new_id)["summary"]["days"] == 50

    def test_a_merge_can_be_complemented_again(self, client, engineer_headers):
        base_id = ready_base(client, engineer_headers)
        middle = upload_over(client, engineer_headers, base_id, following()).json()["id"]
        run_etl(client)
        client.post(f"{DATASETS}/{middle}/confirm", headers=engineer_headers)
        run_etl(client)
        client.portal.call(finish_training, client)
        last = upload_over(client, engineer_headers, middle, following(start=datetime(2026, 3, 10))).json()["id"]
        run_etl(client)
        client.post(f"{DATASETS}/{last}/confirm", headers=engineer_headers)
        run_etl(client)
        assert dataset(client, engineer_headers, last)["summary"]["date_to"] == "2026-04-08"

    def test_only_a_dataset_waiting_for_confirmation_can_be_confirmed(self, client, engineer_headers):
        base_id = ready_base(client, engineer_headers)
        assert client.post(f"{DATASETS}/{base_id}/confirm", headers=engineer_headers).status_code == 400
        assert client.post(f"{DATASETS}/999/confirm", headers=engineer_headers).status_code == 404

    def test_confirming_is_refused_while_a_training_is_in_progress(self, client, engineer_headers):
        base_id = ready_base(client, engineer_headers)
        new_id = upload_over(client, engineer_headers, base_id, following()).json()["id"]
        run_etl(client)
        other = uploaded(client, engineer_headers, BASE)  # becomes a training in progress once cleaned
        run_etl(client)
        assert dataset(client, engineer_headers, other)["upload_status"] == "ready"
        response = client.post(f"{DATASETS}/{new_id}/confirm", headers=engineer_headers)
        assert response.status_code == 400 and "training is in progress" in response.json()["detail"]


class TestRefuseTheMerge:
    def reject(self, client, headers, sheets, cause):
        base_id = ready_base(client, headers)
        new_id = upload_over(client, headers, base_id, sheets).json()["id"]
        run_etl(client)
        body = dataset(client, headers, new_id)
        assert body["upload_status"] == "failed" and cause in body["error_message"], body["error_message"]
        assert get_task_queue().pending(ETL_QUEUE) == []

    def test_a_gap_larger_than_the_interpolation_limit(self, client, engineer_headers):
        self.reject(client, engineer_headers, following(after_gap=13), "13 days without records")

    def test_a_file_that_adds_no_day_after_the_base(self, client, engineer_headers):
        self.reject(client, engineer_headers, following(days=5, after_gap=-20), "adds no days after 2026-01-30")

    def test_different_cells_than_the_dataset_it_complements(self, client, engineer_headers):
        base_id = ready_base(client, engineer_headers)
        new_id = upload_over(client, engineer_headers, base_id, following(cells=[1, 2, 3])).json()["id"]
        run_etl(client)
        client.post(f"{DATASETS}/{new_id}/confirm", headers=engineer_headers)
        run_etl(client)
        assert "cells of section A differ" in dataset(client, engineer_headers, new_id)["error_message"]


class TestRulesOfEveryUpload:
    def test_dates_after_today_are_refused(self, client, engineer_headers):
        dataset_id = uploaded(client, engineer_headers, {"EL A": section_rows(days=30, start=datetime(2999, 1, 1))})
        run_etl(client)
        body = dataset(client, engineer_headers, dataset_id)
        assert body["upload_status"] == "failed" and "dates after today" in body["error_message"]

    def test_the_file_needs_900_days_unless_it_is_merged(self, client, engineer_headers, monkeypatch):
        monkeypatch.setattr("worker.etl.config.MIN_DAYS", 900)
        dataset_id = uploaded(client, engineer_headers, BASE)
        run_etl(client)
        body = dataset(client, engineer_headers, dataset_id)
        assert body["upload_status"] == "failed" and "at least 900 are needed" in body["error_message"]
