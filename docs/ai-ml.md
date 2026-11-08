# AI / ML

**Models are trained and evaluated using synthetic demonstration data and are not clinically validated.**

## Pipeline
1. `ml/data/generator.py` — deterministic synthetic vitals across 12 scenarios (normal, gradual
   deterioration, fever, respiratory deterioration, cardiac stress, post-surgery recovery, recovery,
   sensor noise, missing readings, delayed readings, device failure, connectivity loss). Splits are
   **grouped by `patient_id`** — no patient appears in more than one of train/val/test (see
   `tests/test_data_generator.py::test_no_patient_in_two_splits`).
2. `ml/training/train.py` — three models: LOW/MEDIUM/HIGH risk classifier, 24h deterioration binary
   classifier, 48h deterioration binary classifier. Metrics (precision/recall/F1/confusion
   matrix/ROC-AUC/class distribution) written to `evidence/metrics.json`.
3. `ml/inference/predict.py` — loads the saved artifacts and exposes `get_default_model().predict(features)`.
4. `ml/explainability/explain.py` — SHAP if installed, otherwise a deterministic feature-occlusion
   fallback. The method actually used is always reported, e.g. `"Explanation method: SHAP"` or
   `"Explanation method: feature occlusion fallback"` — never claimed as SHAP when it wasn't used.
5. `services/risk_engine/engine.py` — combines the model output with `rules.py`'s **unconditional**
   hard-threshold safety net: even a confident model prediction cannot suppress an emergency
   escalation if a vital is outside a hard-coded critical band.

## Known metric caveats (see `evidence/*.md` and `STATUS.md` for full detail)
- `deteriorates_48h` model: positive-class prevalence in the test set is ~0.6%; reported metrics are
  not trustworthy at that base rate and must not be presented as if they were.
- `risk_class` model's ~99.5% accuracy reflects an easy synthetic-label mapping (the label is largely
  a deterministic function of the same vitals used as features), not real-world clinical performance.
  Any UI showing this number must show the caveat next to it, not standalone.

## Model-unavailable behavior
If `ml/artifacts/*.joblib` are missing or fail to load, `services/risk_engine/engine.assess()` catches
`ModelUnavailable` and falls back to `rules.rule_based_assessment()`, marking `method: "rules"` in the
response and prefixing the explanation. It never crashes and never silently fabricates a risk score.
