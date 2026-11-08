"""services.risk_engine — turns a features dict into the standard risk-assessment contract:

    {risk_level, probability, contributing_factors, explanation, trend, recommended_escalation, forecast}

Always tries the trained model first (ml.inference.predict); on ModelUnavailable it falls back to
services.risk_engine.rules.rule_based_assessment so the system still produces a usable, labeled assessment
with the AI down. The hard-threshold safety net (rules.check_hard_thresholds) runs UNCONDITIONALLY, even
when the model is available and confident, and can force recommended_escalation to "emergency" regardless
of what either the model or the rule score says — a statistical model must never be the only thing standing
between a critical vital sign and an escalation.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field

from ml.inference.predict import get_default_model, ModelUnavailable
from ml.explainability.explain import explain
from .rules import check_hard_thresholds, trend_from_features, rule_based_assessment

DISCLAIMER = ("Clinical decision-support prototype — not a medical diagnosis or emergency-response "
              "substitute. Always use clinical judgement and contact emergency services if in doubt.")

ESCALATION_LEVELS = ("routine_monitoring", "caregiver_review", "escalate_to_doctor", "emergency")


@dataclass
class RiskAssessment:
    risk_level: str                      # LOW | MEDIUM | HIGH
    probability: float                    # confidence in risk_level, 0-1
    contributing_factors: list            # [{feature, value, contribution, direction, reason?}]
    explanation: str
    trend: dict
    recommended_escalation: str           # one of ESCALATION_LEVELS
    forecast: dict                        # {"deterioration_24h_probability", "deterioration_48h_probability", "basis"}
    method: str                           # "model" | "rules"
    hard_threshold_breaches: list
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return asdict(self)


def _explanation_text(risk_level: str, probability: float, factors: list, method: str) -> str:
    if not factors:
        return f"Risk assessed as {risk_level} ({probability:.0%} confidence). No standout contributing factors identified."
    top = factors[:3]
    parts = [f"{f['feature'].replace('_', ' ')}" + (f" ({f['reason']})" if f.get("reason") else f"={f['value']:.1f}")
            for f in top]
    basis = "the trained risk model" if method == "model" else "rule-based scoring (AI model unavailable)"
    return (f"Risk assessed as {risk_level} ({probability:.0%} confidence) using {basis}, "
           f"primarily driven by: {'; '.join(parts)}.")


def _escalation_for(risk_level: str, det24: float | None, breaches: list) -> str:
    if breaches:
        return "emergency"
    if risk_level == "HIGH" or (det24 is not None and det24 >= 0.65):
        return "escalate_to_doctor"
    if risk_level == "MEDIUM" or (det24 is not None and det24 >= 0.35):
        return "caregiver_review"
    return "routine_monitoring"


def assess(features: dict, top_k_factors: int = 6) -> RiskAssessment:
    """features: output of ml.features.engineering.build_features(...)[0]."""
    breaches = check_hard_thresholds(features)
    trend = trend_from_features(features)
    model = get_default_model()
    try:
        pred = model.predict(features)
        factors = []
        exp = explain(model.risk_clf, pred.feature_vector, model.feature_names, pred.risk_class,
                     features, top_k=top_k_factors)
        for a in exp.top_factors:
            factors.append({"feature": a.feature, "value": a.value, "contribution": a.contribution,
                            "direction": a.direction})
        det24, det48 = pred.deterioration_24h_probability, pred.deterioration_48h_probability
        risk_level, probability, method = pred.risk_class, pred.risk_probabilities[pred.risk_class], "model"
        forecast = {"deterioration_24h_probability": det24, "deterioration_48h_probability": det48,
                   "basis": f"binary classifiers ({exp.method}-explained)",
                   "explanation_method": exp.method}
    except ModelUnavailable as e:
        r = rule_based_assessment(features)
        risk_level, probability, factors, method = r["risk_level"], r["probability"], r["contributing_factors"], "rules"
        det24 = None
        forecast = {"deterioration_24h_probability": None, "deterioration_48h_probability": None,
                   "basis": f"model unavailable ({e}); no ML-based forecast possible", "explanation_method": "rules"}
        breaches = r["hard_threshold_breaches"] or breaches

    escalation = _escalation_for(risk_level, det24, breaches)
    explanation = _explanation_text(risk_level, probability, factors, method)
    if breaches:
        explanation += (" SAFETY OVERRIDE: " + "; ".join(
            f"{b['vital']}={b['value']} outside safe range {b['band']}" for b in breaches))
    return RiskAssessment(risk_level=risk_level, probability=round(float(probability), 3),
                          contributing_factors=factors, explanation=explanation, trend=trend,
                          recommended_escalation=escalation, forecast=forecast, method=method,
                          hard_threshold_breaches=breaches)
