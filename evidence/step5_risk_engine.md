# Step 5 — services/risk_engine — VERIFIED

Command: `PYTHONPATH=. python3 -m unittest tests.test_risk_engine -v` -> 18/18 pass.

## What it composes
`assess(features)` returns the exact contract from the brief:
`{risk_level, probability, contributing_factors, explanation, trend, recommended_escalation, forecast}`
(plus `method`, `hard_threshold_breaches`, `disclaimer` for transparency).

- **Model path** (default, when `ml/artifacts/` is present and loadable): uses `ml.inference.predict` for
  risk_level/probability/forecast and `ml.explainability.explain` for contributing_factors. Verified against
  the REAL trained artifacts from Step 3/4, not mocks: normal vitals -> LOW/routine_monitoring; severely
  abnormal vitals (HR 132, SpO2 91, temp 39.2°C, RR 28, on 2+ comorbidities, age 82) -> HIGH with escalation
  to at least escalate_to_doctor.
- **Rules fallback path**: exercised for real by monkeypatching `ml.inference.predict._default_model` to
  point at a nonexistent artifact directory (`TestAssessFallbackToRules`), which genuinely raises
  `ModelUnavailable` and is caught -- this is not a mocked function call, it is the real failure path. In
  that state `forecast.deterioration_*_probability` is honestly `None` (no ML available to produce a
  forecast) rather than a fabricated number, and `method` is reported as `"rules"` so the UI can show an
  "AI unavailable" indicator per the OFFLINE-banner requirement in Step 9.
- **Hard-threshold safety net**: `rules.check_hard_thresholds` runs unconditionally in both paths.
  `test_safety_override_forces_emergency_even_if_model_disagreed` and
  `test_hard_breach_still_forces_emergency_without_model` confirm a critical vital (e.g. SpO2 80-84%) always
  forces `recommended_escalation == "emergency"` and is called out in the explanation text with
  "SAFETY OVERRIDE", regardless of what the model/rule score alone would have said. This is a deliberate
  design choice: a statistical model must never be the sole gate on an emergency escalation.

## Trend
`trend_from_features` reuses the slope features `ml.features.engineering` already computes (no new raw-data
pass needed), scores each of heart_rate/spo2/temperature/resp_rate/activity by whether its direction of
change is clinically worse, and produces one overall `deterioration_score` in [-1, 1] plus a per-vital
breakdown. Verified: a rising heart rate and a falling SpO2 both push the score toward "worsening"
independently (`TestTrend`). Limitation, stated rather than hidden: systolic/diastolic BP are excluded from
the trend score because both high and low extremes are dangerous (a signed slope alone doesn't say which
direction is "worse" for blood pressure) — they are still covered by the hard-threshold and n_abnormal
checks, just not by the directional trend score.

## Explanation text
A short natural-language string is generated from the same contributing_factors used in the structured
output (no separate/inconsistent narrative), states which method produced the assessment, and appends the
safety-override note verbatim when a hard threshold was breached.

## Forecast
When the model is available, forecast is the model's own 24h/48h deterioration probabilities (Step 3),
labeled with which explainability method annotated them. This is a genuine model output, not a
hand-authored curve. Known limitation carried over from Step 3: the 48h probability's underlying model has
very few positive training examples (see evidence/step3_training.md) — its number is reported honestly but
should not be presented to a user as equally reliable as the 24h figure.
