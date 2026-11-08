"""Held-out evaluation of the ML risk model against the transparent NEWS2 baseline.

DATA: SYNTHETIC (same physiology engine that trained the model). This is an engineering sanity check of the
metrics pipeline and relative behaviour, NOT clinical validation: scores will be optimistic because train and test
share a generator. The same functions run on real data via ml/evaluation/real_data_check.py once datasets are present.

Protocol: patients are split by id (same split as training). Alarm thresholds for fixed alarm budgets are fitted on
the VALIDATION patients and applied unchanged to TEST patients. Event = first time latent severity >= 0.66 (HIGH).
Positive row label = deteriorates_24h. NEWS2 uses only the 'last' vitals (no O2/consciousness data: assumed air/Alert).

Run:  python -m ml.evaluation.run_eval            (writes evidence/eval_synthetic.json + .md)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.generator import HIGH_S, STEP_MINUTES, generate_dataset, group_split
from ml.evaluation.metrics import calibration, discrimination, evaluate_policy, threshold_for_alarm_budget
from ml.inference.predict import get_default_model
from services.risk_engine.news2 import news2

EVIDENCE = Path(__file__).resolve().parents[2] / "evidence"
STRIDE = 2
BUDGETS = (0.5, 1.0, 2.0, 4.0)


def news2_series(df: pd.DataFrame) -> np.ndarray:
    out = []
    for r in df.itertuples(index=False):
        out.append(news2({"heart_rate": r.heart_rate_last, "spo2": r.spo2_last, "resp_rate": r.resp_rate_last,
                          "systolic_bp": r.systolic_bp_last, "temperature": r.temperature_last})["score"])
    return np.asarray(out, dtype=float)


def ml_series(df: pd.DataFrame, model) -> np.ndarray:
    from ml.features.engineering import FEATURE_NAMES
    X = model.scaler.transform(df[list(FEATURE_NAMES)].values.astype(float))
    clf = model.bin_clf["deteriorates_24h"]
    return clf.predict_proba(X)[:, list(clf.classes_).index(1)]


def to_patients(df: pd.DataFrame, score_col: str) -> list[dict]:
    pts = []
    for pid, g in df.groupby("patient_id", sort=False):
        g = g.sort_values("t_index")
        t_h = g["t_index"].to_numpy() * STEP_MINUTES / 60.0
        high = g["severity"].to_numpy() >= HIGH_S
        event_h = float(t_h[np.argmax(high)]) if high.any() else None
        pts.append({"patient_id": pid, "scenario": g["scenario"].iloc[0], "times_h": t_h,
                    "scores": g[score_col].to_numpy(), "event_h": event_h})
    return pts


def run(n_per_scenario: int = 60, n_steps: int = 400, seed: int = 2026) -> dict:
    df = group_split(generate_dataset(n_per_scenario, n_steps, seed, row_stride=STRIDE), seed=seed)
    model = get_default_model(); model.load()
    df["ml"] = ml_series(df, model)
    df["news2"] = news2_series(df)
    val, test = df[df.split == "val"], df[df.split == "test"]
    lab = test[test.label_horizon_24h_available == 1]

    res = {"data": "SYNTHETIC - not clinical validation", "seed": seed, "test_patients": int(test.patient_id.nunique()),
           "test_rows": int(len(test)), "positive_label": "deteriorates_24h",
           "discrimination_24h": {"ml": discrimination(lab.deteriorates_24h, lab.ml),
                                  "news2": discrimination(lab.deteriorates_24h, lab.news2)},
           "calibration_ml_24h": calibration(lab.deteriorates_24h, lab.ml),
           "calibration_note": "NEWS2 is an ordinal score, not a probability, so calibration/Brier apply to ML only."}

    pv, pt = to_patients(val, "ml"), to_patients(test, "ml")
    nv, nt = to_patients(val, "news2"), to_patients(test, "news2")
    res["event_patients_test"] = sum(p["event_h"] is not None for p in pt)
    res["control_patients_test"] = sum(p["event_h"] is None for p in pt)
    budget = []
    for k in BUDGETS:
        row = {"target_alarms_per_patient_day": k}
        for name, v, t in (("ml", pv, pt), ("news2", nv, nt)):
            thr = threshold_for_alarm_budget(v, k)
            row[name] = evaluate_policy(t, thr)
        budget.append(row)
    res["fixed_alarm_budget"] = budget
    res["news2_standard_thresholds"] = {f">={thr}": evaluate_policy(nt, thr) for thr in (3, 5, 7)}
    return res


def to_markdown(r: dict) -> str:
    L = ["# Synthetic held-out evaluation: ML risk vs NEWS2 baseline", "",
         "> **SYNTHETIC DATA. Not clinical validation.** Train and test share one generator, so numbers are optimistic.", "",
         f"Test patients: {r['test_patients']} ({r['event_patients_test']} reach HIGH severity, {r['control_patients_test']} never do); rows: {r['test_rows']}.", "",
         "## Discrimination (deteriorates within 24 h)", "| Score | ROC-AUC | PR-AUC | prevalence |", "|---|---|---|---|"]
    for k, d in r["discrimination_24h"].items():
        L.append(f"| {k} | {d['roc_auc']:.3f} | {d['pr_auc']:.3f} | {d['prevalence']:.3f} |")
    c = r["calibration_ml_24h"]
    L += ["", f"## Calibration (ML)  Brier {c['brier']:.4f} (constant-prevalence reference {c['brier_reference_constant_prevalence']:.4f}), ECE {c['ece']:.3f}",
          "| bin | n | mean predicted | observed |", "|---|---|---|---|"]
    L += [f"| {b['bin']} | {b['n']} | {b['mean_predicted']:.2f} | {b['observed_rate']:.2f} |" for b in c["bins"]]
    L += ["", "## Fixed alarm budget (thresholds fitted on validation patients, 6 h refractory, true alarm = within 48 h before event)",
          "| budget /pt/day | score | realised alarms /pt/day | false alarms /pt/day | sensitivity | median lead (h) |", "|---|---|---|---|---|---|"]
    for row in r["fixed_alarm_budget"]:
        for n in ("ml", "news2"):
            d = row[n]
            lead = f"{d['median_lead_time_h']:.1f}" if d["median_lead_time_h"] is not None else "n/a"
            L.append(f"| {row['target_alarms_per_patient_day']} | {n} | {d['alarms_per_patient_day']:.2f} | {d['false_alarms_per_patient_day']:.2f} | {d['sensitivity']:.2f} | {lead} |")
    L += ["", "## NEWS2 at standard thresholds", "| rule | alarms /pt/day | false alarms /pt/day | sensitivity | median lead (h) |", "|---|---|---|---|---|"]
    for k, d in r["news2_standard_thresholds"].items():
        lead = f"{d['median_lead_time_h']:.1f}" if d["median_lead_time_h"] is not None else "n/a"
        L.append(f"| NEWS2 {k} | {d['alarms_per_patient_day']:.2f} | {d['false_alarms_per_patient_day']:.2f} | {d['sensitivity']:.2f} | {lead} |")
    return "\n".join(L) + "\n"


def main():
    r = run()
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / "eval_synthetic.json").write_text(json.dumps(r, indent=2, default=float))
    (EVIDENCE / "eval_synthetic.md").write_text(to_markdown(r))
    print(to_markdown(r))


if __name__ == "__main__":
    main()
