"""Per-prediction feature attribution.

Uses SHAP's TreeExplainer when the `shap` package is importable (it is NOT installed in the dev sandbox
this was built in -- verified with `python3 -c "import shap"` failing -- so the occlusion path below is the
one actually exercised by tests here). If SHAP is available, prefer it: it is the theoretically grounded
method (Shapley values). The occlusion fallback is a reasonable, dependency-free approximation, not
equivalent, and every result says which one produced it via `method`.

Occlusion attribution definition: for a fitted classifier and a specific instance x (already scaled),
predicting probability p0 for the target class, each feature i is knocked out by setting it to the
dataset's mean in scaled space (0.0, since StandardScaler was fit on the training set) giving x_i, and the
model is re-scored to get p_i. The feature's contribution is defined as (p0 - p_i): how much the model's
confidence in the target class RELIES on that feature having its actual value rather than the population
average. Positive = pushed the prediction toward the target class; negative = pushed away from it.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

import numpy as np

try:
    import shap as _shap
    SHAP_AVAILABLE = True
except ImportError:
    _shap = None
    SHAP_AVAILABLE = False


@dataclass
class Attribution:
    feature: str
    value: float          # the feature's actual (unscaled) value, for human display
    contribution: float   # signed; magnitude is only comparable within one explanation, not across calls
    direction: str         # "increases_risk" | "decreases_risk"


@dataclass
class Explanation:
    method: str            # "shap" | "occlusion"
    target_class: str      # e.g. "HIGH", or "1" for a binary deterioration target
    base_value: float       # p0: model's probability for target_class on the actual instance
    top_factors: list       # list[Attribution], sorted by |contribution| descending
    note: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["top_factors"] = [asdict(a) if not isinstance(a, dict) else a for a in self.top_factors]
        return d


def _class_index(clf, target_label) -> int:
    classes = list(clf.classes_)
    if target_label not in classes:
        raise ValueError(f"target_label {target_label!r} not in model classes {classes}")
    return classes.index(target_label)


def _occlusion(clf, xs_row: np.ndarray, feature_names, target_label, raw_features: dict, top_k: int) -> Explanation:
    idx = _class_index(clf, target_label)
    p0 = float(clf.predict_proba(xs_row.reshape(1, -1))[0, idx])
    contributions = np.zeros(len(feature_names))
    batch = np.repeat(xs_row.reshape(1, -1), len(feature_names), axis=0)
    for i in range(len(feature_names)):
        batch[i, i] = 0.0  # knock out feature i to the (scaled) population mean
    probs = clf.predict_proba(batch)[:, idx]
    contributions = p0 - probs
    order = np.argsort(-np.abs(contributions))[:top_k]
    factors = [Attribution(
        feature=feature_names[i], value=float(raw_features.get(feature_names[i], float("nan"))),
        contribution=float(contributions[i]),
        direction="increases_risk" if contributions[i] > 0 else "decreases_risk",
    ) for i in order]
    return Explanation(method="occlusion", target_class=str(target_label), base_value=p0,
                       top_factors=factors,
                       note="SHAP not installed; contribution = drop in predicted probability when this "
                            "feature is reset to the population-average (scaled) value. Approximate, not "
                            "an exact Shapley decomposition.")


def _shap_explain(clf, xs_row: np.ndarray, feature_names, target_label, raw_features: dict, top_k: int) -> Explanation:
    idx = _class_index(clf, target_label)
    p0 = float(clf.predict_proba(xs_row.reshape(1, -1))[0, idx])
    explainer = _shap.TreeExplainer(clf)
    sv = explainer.shap_values(xs_row.reshape(1, -1))
    vals = sv[idx][0] if isinstance(sv, list) else np.asarray(sv)[0, :, idx]
    order = np.argsort(-np.abs(vals))[:top_k]
    factors = [Attribution(
        feature=feature_names[i], value=float(raw_features.get(feature_names[i], float("nan"))),
        contribution=float(vals[i]), direction="increases_risk" if vals[i] > 0 else "decreases_risk",
    ) for i in order]
    return Explanation(method="shap", target_class=str(target_label), base_value=p0, top_factors=factors,
                       note="Exact Shapley-value decomposition via shap.TreeExplainer.")


def explain(clf, xs_row: np.ndarray, feature_names, target_label, raw_features: dict, top_k: int = 6) -> Explanation:
    """clf: a fitted sklearn classifier with predict_proba + classes_ (RandomForest here).
    xs_row: the SCALED 1D feature vector for this instance (same scaling used at training time).
    target_label: which class's probability to explain (e.g. "HIGH", or 1 for binary targets).
    raw_features: unscaled feature dict, for human-readable values in the output."""
    if SHAP_AVAILABLE:
        try:
            return _shap_explain(clf, xs_row, feature_names, target_label, raw_features, top_k)
        except Exception:
            pass  # fall through to occlusion rather than fail the whole prediction over an explainer bug
    return _occlusion(clf, xs_row, feature_names, target_label, raw_features, top_k)
