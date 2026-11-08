"""Evaluate the NEWS2 baseline on real PhysioNet-2019-format data (the ML model is NOT evaluated here: it needs the
simulator's engineered windows and was trained on synthetic data, so applying it to real data would be unvalidated).

Usage: python -m ml.evaluation.real_data_check /path/to/training_setA [--limit 2000]
Writes evidence/eval_real_news2.json. NEVER RUN on real data in the build sandbox (dataset not downloadable offline).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ml.data.physionet import load_directory
from ml.evaluation.metrics import discrimination, evaluate_policy
from services.risk_engine.news2 import news2


def patient_scores(pt: dict) -> dict:
    f = pt["frame"]
    sc = []
    for r in f.itertuples(index=False):
        vit = {k: (None if np.isnan(getattr(r, k)) else float(getattr(r, k)))
               for k in ("heart_rate", "spo2", "resp_rate", "systolic_bp", "temperature")}
        sc.append(news2({k: v for k, v in vit.items() if v is not None})["score"])
    return {"times_h": f["t_h"].to_numpy(), "scores": np.asarray(sc, float), "event_h": pt["event_h"]}


def run(directory: str, limit: int | None = None) -> dict:
    pts = load_directory(directory, limit)
    ps = [patient_scores(p) for p in pts]
    y = np.concatenate([(p["times_h"] >= (p["event_h"] - 24)) & (p["times_h"] < p["event_h"]) if p["event_h"] is not None
                        else np.zeros(len(p["times_h"]), bool) for p in ps]).astype(int)
    s = np.concatenate([p["scores"] for p in ps])
    return {"data": "REAL (PhysioNet 2019 format) - NEWS2 only; not clinical validation", "patients": len(ps),
            "event_patients": sum(p["event_h"] is not None for p in ps),
            "discrimination_24h_before_label": discrimination(y, s),
            "news2_thresholds": {f">={t}": evaluate_policy(ps, t, refractory_h=6.0, lookback_h=24.0) for t in (3, 5, 7)}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    r = run(a.directory, a.limit)
    out = Path(__file__).resolve().parents[2] / "evidence" / "eval_real_news2.json"
    out.write_text(json.dumps(r, indent=2, default=float))
    print(json.dumps(r, indent=2, default=float))
