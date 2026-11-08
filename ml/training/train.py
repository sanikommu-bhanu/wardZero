"""Train the risk models on ml/data/generator output and save artifacts + evidence/metrics.json.

Models (all scikit-learn, no external services):
  risk_class          -> RandomForestClassifier, 3-class LOW/MEDIUM/HIGH
  deteriorates_24h     -> RandomForestClassifier, binary
  deteriorates_48h     -> RandomForestClassifier, binary (class_weight="balanced": rare positive class,
                           see evidence/metrics.json deteriorates_48h.positive_rate)

Splits come from the generator's own group_split (by patient_id) so no patient's readings appear in more
than one of train/val/test. Val is used only to report a held-out snapshot during development; test is the
number reported as "the" metrics. Everything is written to ml/artifacts/ and evidence/metrics.json so the
numbers in this file are reproducible by rerunning `python -m ml.training.train`.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (precision_recall_fscore_support, confusion_matrix, roc_auc_score,
                              accuracy_score, classification_report)
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss

from ml.data.generator import generate_dataset, group_split
from ml.features.engineering import FEATURE_NAMES

ARTIFACT_DIR = Path("ml/artifacts")
EVIDENCE_PATH = Path("evidence/metrics.json")
RISK_CLASSES = ["LOW", "MEDIUM", "HIGH"]


def _prep_xy(df: pd.DataFrame, target: str):
    X = df[list(FEATURE_NAMES)].values.astype(float)
    y = df[target].values
    return X, y


def _multiclass_metrics(y_true, y_pred, proba, classes) -> dict:
    p, r, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=classes).tolist()
    try:
        auc = roc_auc_score(pd.get_dummies(y_true, columns=classes).reindex(columns=classes, fill_value=0).values,
                            proba, multi_class="ovr")
    except ValueError:
        auc = None
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "per_class": {c: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f1[i]),
                          "support": int(support[i])} for i, c in enumerate(classes)},
        "macro_f1": float(f1.mean()),
        "confusion_matrix": {"labels": classes, "matrix": cm},
        "roc_auc_ovr_macro": auc,
    }


def _binary_metrics(y_true, y_pred, proba1) -> dict:
    y_true = np.asarray(y_true)
    p, r, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1], zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
    auc = ap = brier = None
    if len(set(y_true)) > 1:
        auc = float(roc_auc_score(y_true, proba1))
        ap = float(average_precision_score(y_true, proba1))   # PR-AUC: the honest metric for rare positives
        brier = float(brier_score_loss(y_true, proba1))      # calibration quality (lower = better)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "positive_rate": float(np.mean(y_true)),
        "per_class": {"0": {"precision": float(p[0]), "recall": float(r[0]), "f1": float(f1[0]), "support": int(support[0])},
                     "1": {"precision": float(p[1]), "recall": float(r[1]), "f1": float(f1[1]), "support": int(support[1])}},
        "f1_positive": float(f1[1]),
        "confusion_matrix": {"labels": [0, 1], "matrix": cm},
        "roc_auc": auc, "pr_auc": ap, "brier": brier,
    }


def train_all(n_patients_per_scenario: int = 60, n_steps: int = 400, seed: int = 2026,
              artifact_dir: Path | None = None, evidence_path: Path | None = None) -> dict:
    """Train and write artifacts.

    `artifact_dir` / `evidence_path` default to the module-level real paths (ml/artifacts,
    evidence/metrics.json) so `python -m ml.training.train` behaves exactly as before. Tests pass a
    temp directory instead so a small toy training run in the test suite never overwrites the real,
    full-size production artifacts — see tests/test_training.py.
    """
    artifact_dir = Path(artifact_dir) if artifact_dir is not None else ARTIFACT_DIR
    evidence_path = Path(evidence_path) if evidence_path is not None else EVIDENCE_PATH

    df = generate_dataset(n_patients_per_scenario, n_steps, seed, row_stride=2)
    df = group_split(df, seed=seed)
    train, val, test = (df[df["split"] == s].reset_index(drop=True) for s in ("train", "val", "test"))

    scaler = StandardScaler().fit(train[list(FEATURE_NAMES)].values.astype(float))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, artifact_dir / "scaler.joblib")
    joblib.dump(list(FEATURE_NAMES), artifact_dir / "feature_names.joblib")

    metrics: dict = {"feature_count": len(FEATURE_NAMES), "dataset": {
        "n_rows": len(df), "n_patients": df["patient_id"].nunique(),
        "split_sizes_rows": {s: int((df["split"] == s).sum()) for s in ("train", "val", "test")},
        "split_sizes_patients": df.groupby("split")["patient_id"].nunique().to_dict(),
        "seed": seed, "patients_per_scenario": n_patients_per_scenario, "n_steps": n_steps,
    }, "models": {}}

    # --- 3-class risk model ---------------------------------------------------------------------
    Xtr, ytr = _prep_xy(train, "risk_class")
    Xte, yte = _prep_xy(test, "risk_class")
    clf = RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=5,
                                 class_weight="balanced", random_state=seed, n_jobs=-1)
    clf.fit(scaler.transform(Xtr), ytr)
    classes = list(clf.classes_)
    proba = clf.predict_proba(scaler.transform(Xte))
    pred = clf.predict(scaler.transform(Xte))
    metrics["models"]["risk_class"] = _multiclass_metrics(yte, pred, proba, classes)
    metrics["models"]["risk_class"]["classes_order"] = classes
    joblib.dump(clf, artifact_dir / "risk_class_model.joblib")

    # --- binary deterioration models -------------------------------------------------------------
    for target in ("deteriorates_24h", "deteriorates_48h"):
        # Only rows whose full look-ahead window exists are labeled; rows near the end of a trajectory are
        # UNKNOWN, not "negative" (previously they were silently labeled 0, biasing the positive rate).
        avail = "label_horizon_24h_available" if target.endswith("24h") else "label_horizon_48h_available"
        Xtr, ytr = _prep_xy(train[train[avail] == 1], target)
        Xte, yte = _prep_xy(test[test[avail] == 1], target)
        if len(ytr) == 0 or len(set(ytr)) < 2 or len(yte) == 0:
            metrics["models"][target] = {"skipped": "trajectories too short for this look-ahead horizon, or a "
                                                     "single class — train with a larger n_steps"}
            continue
        bclf = RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=5,
                                      class_weight="balanced", random_state=seed, n_jobs=-1)
        bclf.fit(scaler.transform(Xtr), ytr)
        proba1 = bclf.predict_proba(scaler.transform(Xte))[:, list(bclf.classes_).index(1)] \
            if 1 in bclf.classes_ else np.zeros(len(Xte))
        pred = bclf.predict(scaler.transform(Xte))
        metrics["models"][target] = _binary_metrics(yte, pred, proba1)
        # Baselines so the number means something: a linear model, and the no-skill PR-AUC (= prevalence).
        lr = LogisticRegression(max_iter=500, class_weight="balanced").fit(scaler.transform(Xtr), ytr)
        lr_p = lr.predict_proba(scaler.transform(Xte))[:, 1]
        metrics["models"][target]["baseline_logistic_regression"] = {
            "roc_auc": float(roc_auc_score(yte, lr_p)) if len(set(yte)) > 1 else None,
            "pr_auc": float(average_precision_score(yte, lr_p)) if len(set(yte)) > 1 else None}
        metrics["models"][target]["no_skill_pr_auc"] = float(np.mean(yte))
        joblib.dump(bclf, artifact_dir / f"{target}_model.joblib")

    # --- feature importance (model-native; SHAP/occlusion is done at inference time, per-prediction) --
    metrics["models"]["risk_class"]["global_feature_importance_top15"] = sorted(
        zip(FEATURE_NAMES, clf.feature_importances_.tolist()), key=lambda kv: -kv[1])[:15]

    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(metrics, indent=2, default=str))
    manifest = {"risk_classes": RISK_CLASSES, "feature_names": list(FEATURE_NAMES),
               "artifact_dir": str(artifact_dir), "seed": seed}
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return metrics


if __name__ == "__main__":
    m = train_all()
    print(json.dumps({k: v for k, v in m.items() if k != "dataset"} | {"dataset": m["dataset"]}, indent=2)[:3000])
    print("... full metrics written to", EVIDENCE_PATH)
