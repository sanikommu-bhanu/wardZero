# Step 4 — ml/inference + ml/explainability — VERIFIED

## ml/inference/predict.py
Command: `PYTHONPATH=. python3 -m unittest tests.test_inference -v` -> 8/8 pass, run against the REAL
artifacts trained in Step 3 (not mocks). Confirms: loads scaler+3 models+manifest; raises ModelUnavailable
(not a silent failure) when the artifact directory is missing; risk probabilities sum to 1; a plausible
normal-vitals patient is scored LOW risk and a clearly abnormal one (SpO2 83%, HR 132, temp 39.4°C, on
5 comorbidities) is scored HIGH risk with HIGH-class probability exceeding LOW-class probability.

## ml/explainability/explain.py
Verified SHAP is NOT importable in this sandbox: `python3 -c "import shap"` -> ModuleNotFoundError (checked
fresh in this step, not assumed from earlier sessions). So every explanation produced and tested here used
the occlusion fallback; `test_shap_confirmed_unavailable_in_this_sandbox` pins that fact so a future run in
a different environment would visibly flag if SHAP silently became available and changed which code path
tests are covering. `explain()` prefers SHAP's TreeExplainer whenever `shap` IS importable and only falls
back to occlusion on ImportError or an explainer-time exception — this SHAP branch itself is untested here
since the package cannot be installed (no network) and this is stated rather than glossed over.

Command: `PYTHONPATH=. python3 -m unittest tests.test_explainability -v` -> 9/9 pass. Confirms: method is
always labeled ("occlusion" here); factors sorted by |contribution| descending; base_value matches the
model's own predict_proba for the target class; direction label is internally consistent with the sign of
the contribution; and — the closest thing to a clinical sanity check available without real patient data —
for a simulated patient with severely abnormal vitals, the top attributed factors for HIGH-risk actually
include SpO2/heart-rate/abnormal-count features, not arbitrary ones.

## Caveat recorded during this step (process note, not a code bug)
`ml/training/tests/test_training.py`'s `setUpClass` retrains a tiny (8-patient/scenario) model and
overwrites `ml/artifacts/` as a side effect of being test code that calls the real `train_all()`. Running
`python -m unittest discover -s tests` therefore leaves the toy artifacts on disk afterward, not the
full-size ones referenced in evidence/metrics.json. This was caught in this session (inference/explainability
tests still passed against the toy artifacts, but evidence/metrics.json no longer matched what was on disk)
and fixed by re-running `python -m ml.training.train` (full size) after any full test-suite run. Documented
here so it isn't a surprise later; a cleaner long-term fix is for test_training to use a temp artifact dir
instead of the real one (left as a follow-up, not fixed now to avoid touching already-passing Step 3 code
without being asked).
