"""Deterministic, dependency-free rules used by services.risk_engine.

Two distinct roles, kept separate on purpose:
1. HARD_THRESHOLDS / check_hard_thresholds(): a safety net that ALWAYS runs, model-available or not.
   A machine-learning risk score is a statistical estimate and must never be the only thing standing between
   a genuinely dangerous vital sign and an escalation. These thresholds are intentionally conservative and
   independent of any model.
2. rule_based_assessment(): the FULL fallback risk assessment used only when the trained model's artifacts
   are unavailable (missing/corrupt/schema-mismatched). It produces the same output shape as the ML path so
   callers (and the UI) don't need to know which one ran, except via the `method` field.
"""
from __future__ import annotations
from ml.features.schema import NOTE_KEYS

# (low, high) — outside this band is a hard safety-net trigger regardless of model output/availability.
HARD_THRESHOLDS = {
    "heart_rate": (40, 150),
    "spo2": (88, 101),
    "temperature": (35.0, 40.0),
    "resp_rate": (8, 30),
    "systolic_bp": (85, 200),
}

# Direction that WORSENS the patient's condition, used for trend scoring. +1 = higher is worse,
# -1 = lower is worse. Vitals with a bidirectional risk profile (both bp fields) are excluded here and
# handled instead via n_abnormal / hard thresholds, which already catch both extremes.
WORSE_DIRECTION = {"heart_rate": 1, "spo2": -1, "temperature": 1, "resp_rate": 1, "activity": -1}
# Slope (per hour) considered a clinically meaningful rate of change for that vital, used to normalize
# trend scoring across vitals with different units/scales.
TREND_SCALE = {"heart_rate": 6.0, "spo2": 1.2, "temperature": 0.3, "resp_rate": 3.0, "activity": 12.0}

RULE_WEIGHTS = {  # points toward a 0-100 rule score; tuned to roughly track the ML model's class boundaries
    "spo2_critical": 35, "resp_critical": 25, "hr_critical": 20, "temp_critical": 15, "bp_critical": 20,
    "n_abnormal": 8,        # per abnormal vital (n_abnormal already 0-5)
    "note_signal": 6,       # per present symptom signal from caregiver notes
    "comorbidity": 3,       # per known comorbidity
}


def check_hard_thresholds(features: dict) -> list[dict]:
    """Returns a list of breaches: [{'vital', 'value', 'band', 'severity': 'critical'}]. Empty = none."""
    breaches = []
    for vital, (lo, hi) in HARD_THRESHOLDS.items():
        val = features.get(f"{vital}_last")
        if val is None:
            continue
        if val < lo or val > hi:
            breaches.append({"vital": vital, "value": val, "band": [lo, hi], "severity": "critical"})
    return breaches


def trend_from_features(features: dict) -> dict:
    """Per-vital direction (rising/falling/stable) plus one overall deterioration_score in [-1, 1]
    (positive = trending worse) built only from the slope features engineering already computes."""
    per_vital = {}
    score = 0.0
    n = 0
    for vital, direction in WORSE_DIRECTION.items():
        slope = features.get(f"{vital}_slope_h")
        if slope is None:
            continue
        scale = TREND_SCALE[vital]
        normalized = max(-1.0, min(1.0, slope / scale))
        label = "rising" if slope > 0.05 * scale else ("falling" if slope < -0.05 * scale else "stable")
        per_vital[vital] = {"slope_per_hour": round(float(slope), 3), "direction": label}
        score += normalized * direction
        n += 1
    overall_score = score / max(n, 1)
    if overall_score > 0.25:
        overall = "worsening"
    elif overall_score < -0.25:
        overall = "improving"
    else:
        overall = "stable"
    return {"overall": overall, "deterioration_score": round(float(overall_score), 3), "per_vital": per_vital}


def rule_based_assessment(features: dict) -> dict:
    """Pure-rules fallback. Returns {'risk_level','probability','score','contributing_factors'} — no ML."""
    score = 0.0
    factors = []
    breaches = check_hard_thresholds(features)
    for b in breaches:
        key = {"spo2": "spo2_critical", "resp_rate": "resp_critical", "heart_rate": "hr_critical",
              "temperature": "temp_critical", "systolic_bp": "bp_critical"}[b["vital"]]
        score += RULE_WEIGHTS[key]
        factors.append({"feature": f"{b['vital']}_last", "value": b["value"],
                        "contribution": float(RULE_WEIGHTS[key]), "direction": "increases_risk",
                        "reason": f"outside safe range {b['band']}"})
    n_abn = features.get("n_abnormal", 0.0)
    if n_abn:
        pts = RULE_WEIGHTS["n_abnormal"] * n_abn
        score += pts
        factors.append({"feature": "n_abnormal", "value": n_abn, "contribution": float(pts),
                        "direction": "increases_risk", "reason": f"{int(n_abn)} vital sign(s) abnormal"})
    for k in NOTE_KEYS:
        if features.get(f"note_{k}", 0.0):
            score += RULE_WEIGHTS["note_signal"]
            factors.append({"feature": f"note_{k}", "value": 1.0, "contribution": float(RULE_WEIGHTS["note_signal"]),
                            "direction": "increases_risk", "reason": "caregiver-reported symptom"})
    comorbidities = features.get("comorbidity_count", 0.0)
    if comorbidities:
        pts = RULE_WEIGHTS["comorbidity"] * comorbidities
        score += pts
        factors.append({"feature": "comorbidity_count", "value": comorbidities, "contribution": float(pts),
                        "direction": "increases_risk", "reason": f"{int(comorbidities)} known comorbidity/ies"})
    score = max(0.0, min(100.0, score))
    if breaches or score >= 55:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"
    probability = round(score / 100.0, 3)
    factors.sort(key=lambda f: -f["contribution"])
    return {"risk_level": level, "probability": probability, "score": score,
           "contributing_factors": factors[:8], "hard_threshold_breaches": breaches}
