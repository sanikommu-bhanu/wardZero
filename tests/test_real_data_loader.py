import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.physionet import load_directory, load_psv
from ml.evaluation.metrics import alarm_times, calibration, discrimination, evaluate_policy, threshold_for_alarm_budget
from ml.evaluation.real_data_check import run


def _write(path, n=30, sepsis_at=None, hr=80):
    rows = {"HR": [hr + (40 if sepsis_at and i >= sepsis_at - 8 else 0) for i in range(n)],
            "O2Sat": [97.0] * n, "Temp": [np.nan] + [37.0] * (n - 1), "Resp": [16.0] * n, "SBP": [120.0] * n,
            "SepsisLabel": [1 if sepsis_at is not None and i >= sepsis_at else 0 for i in range(n)]}
    pd.DataFrame(rows).to_csv(path, sep="|", index=False)


class TestRealDataLoader(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp_path = Path(self._td.name)

    def test_load_psv_maps_and_ffills(self):
        p = self.tmp_path / "p1.psv"; _write(p)
        df = load_psv(p)
        assert {"heart_rate", "spo2", "temperature", "resp_rate", "systolic_bp", "t_h"} <= set(df.columns)
        assert np.isnan(df.temperature.iloc[0]) and df.temperature.iloc[1] == 37.0


    def test_missing_columns_rejected(self):
        p = self.tmp_path / "bad.psv"; pd.DataFrame({"HR": [1]}).to_csv(p, sep="|", index=False)
        try:
            load_psv(p)
            assert False
        except ValueError:
            pass


    def test_directory_event_and_check_runs(self):
        _write(self.tmp_path / "a.psv", sepsis_at=20); _write(self.tmp_path / "b.psv")
        pts = load_directory(self.tmp_path)
        assert [p["event_h"] for p in pts] == [20.0, None]
        r = run(str(self.tmp_path))
        assert r["patients"] == 2 and r["event_patients"] == 1 and "REAL" in r["data"]


    def test_empty_directory_raises(self):
        try:
            load_directory(self.tmp_path); self.fail("expected FileNotFoundError")
        except FileNotFoundError:
            pass


    def test_metrics_known_values(self):
        assert discrimination([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])["roc_auc"] == 1.0
        assert discrimination([1, 1], [0.1, 0.2])["roc_auc"] is None
        c = calibration([0, 1, 1, 1], [0.0, 1.0, 1.0, 1.0]); assert c["ece"] == 0.0
        assert alarm_times([0, 1, 2, 7, 8], [1, 1, 1, 1, 1], 1, 6) == [0.0, 7.0]


    def test_policy_lead_time_and_budget(self):
        t = np.arange(0, 100.0)
        ev = {"times_h": t[:60], "scores": np.where(t[:60] > 30, 5, 0), "event_h": 60.0}
        ctl = {"times_h": t, "scores": np.zeros(100), "event_h": None}
        r = evaluate_policy([ev, ctl], 3)
        assert r["sensitivity"] == 1.0 and r["median_lead_time_h"] == 29.0 and r["false_alarms_per_patient_day"] == 0
        thr = threshold_for_alarm_budget([ev, ctl], 0.0)
        assert evaluate_policy([ev, ctl], thr)["alarms_per_patient_day"] == 0

