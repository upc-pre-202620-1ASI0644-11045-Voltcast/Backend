import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from worker.etl.cleaning import database_cell_name
from worker.training import config, vmd
from worker.training.pipeline import _metrics


def series(days=200):
    t = np.arange(days)
    return 3.2 + 0.05 * np.sin(t / 20) + np.random.default_rng(0).normal(0, 0.002, days)


class TestCellNames:
    @pytest.mark.parametrize("celda, name", [("A_c001", "A1"), ("B_c150", "B150"), ("A_c010", "A10")])
    def test_poc_names_map_to_database_names(self, celda, name):
        assert database_cell_name(celda) == name


class TestVmdParameters:
    def test_every_cell_of_the_poc_has_its_pair_and_new_cells_get_the_most_frequent_one(self):
        per_cell, default = vmd.load_vmd_params()
        assert len(per_cell) == 300 and per_cell["A_c001"] == (15, 400.0) and default == (15, 400.0)


class TestFilterSegments:
    def test_filters_only_the_in_service_stretches_long_enough(self):
        x, blocked = series(), np.zeros(200, dtype=bool)
        blocked[100:110] = True  # out of service
        blocked[140:170] = True  # leaves 110..139 (30 days) and 170..199 (30 days), both shorter than the minimum
        out = vmd.filter_segments(x, blocked, 5, 400.0)
        assert np.isnan(out[100:110]).all() and np.isnan(out[140:170]).all()
        assert np.isfinite(out[1:100]).all()  # the first stretch is long enough (its first day is lost when the length is odd)
        assert np.isnan(out[110:140]).all() and np.isnan(out[170:]).all()  # too short to decompose

    def test_the_filtered_signal_follows_the_slow_movement(self):
        x = series()
        out = vmd.filter_segments(x, np.zeros(200, dtype=bool), 5, 400.0)
        assert np.nanmax(np.abs(out - x)) < 0.05


class TestCausalWindow:
    def test_returns_the_last_days_filtered_with_data_up_to_the_origin(self):
        window = vmd.causal_window(series(), np.zeros(200, dtype=bool), 150, 5, 400.0)
        assert window.shape == (config.LOOKBACK_DAYS,) and np.isfinite(window).all()

    def test_is_empty_when_the_origin_is_out_of_service_or_the_stretch_is_short(self):
        blocked = np.zeros(200, dtype=bool)
        blocked[150] = True
        assert np.isnan(vmd.causal_window(series(), blocked, 150, 5, 400.0)).all()
        assert np.isnan(vmd.causal_window(series(), blocked, 180, 5, 400.0)).all()  # 29 days since the stretch began

    def test_does_not_use_data_after_the_origin(self):
        x = series()
        changed = x.copy()
        changed[151:] += 1.0
        same = vmd.causal_window(x, np.zeros(200, dtype=bool), 150, 5, 400.0)
        assert np.allclose(same, vmd.causal_window(changed, np.zeros(200, dtype=bool), 150, 5, 400.0))


class TestMetrics:
    def test_rmse_mae_mape_and_r2(self):
        metrics = _metrics(np.array([3.0, 2.0]), np.array([2.0, 4.0]))
        assert metrics["rmse"] == pytest.approx(np.sqrt(2.5)) and metrics["mae"] == pytest.approx(1.5)
        assert metrics["mape"] == pytest.approx(50.0) and metrics["r2"] == pytest.approx(1 - 5 / 2)


class TestWorkerStartsAlone:
    def test_every_table_the_worker_writes_can_resolve_its_foreign_keys_without_the_api(self, tmp_path):
        """The worker does not import the API, so each table a foreign key points to has to be imported by the worker itself."""
        code = "import worker.main; from shared.infrastructure.persistence.configuration.database_configuration import Base; Base.metadata.sorted_tables"
        env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'x.db'}"}
        done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=Path(__file__).parents[2])
        assert done.returncode == 0, done.stderr[-600:]
