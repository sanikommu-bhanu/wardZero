# Step 3 — ml/training — VERIFIED, with an honest read of the numbers

Command: `PYTHONPATH=. python3 -m unittest tests.test_training -v` -> 4/4 pass (small 8-patient/scenario run).
Command: `PYTHONPATH=. python3 -m ml.training.train` (full run: 60 patients/scenario, 200 steps, seed=2026)
 -> writes ml/artifacts/*.joblib + ml/artifacts/manifest.json + evidence/metrics.json (all real, generated
 by this run, not fabricated -- rerun the command yourself to reproduce them exactly, seed is fixed).

Headline numbers (full detail in evidence/metrics.json):
- risk_class (LOW/MEDIUM/HIGH), RandomForest, test set (45 held-out patients, 8730 rows):
  accuracy 0.995, macro-F1 0.987.
- deteriorates_24h, RandomForest binary: accuracy 0.78, F1(positive)=0.70, ROC-AUC=0.91, positive rate 30%.
- deteriorates_48h, RandomForest binary: ROC-AUC=0.9999(!), F1(positive)=0.92, but positive rate is only
  0.6% of the test set (~16 rows) -- THIS NUMBER IS NOT RELIABLE. A handful of true positives can swing F1
  and AUC wildly; do not present the 48h model's numbers as evidence of real predictive power. It needs
  either (a) longer simulated trajectories so more patients cross the 48h deterioration threshold, or
  (b) a different labeling window, before its metrics mean anything. Documented here rather than hidden.

Why risk_class accuracy is so high (99.5%) -- and why that is NOT a claim of clinical accuracy:
risk_class is a deterministic bucketing of the same latent severity value that drove the simulated vitals
the features are computed from (see ml/data/generator.py: _risk_class(s)). The model is therefore learning
an easy, near-deterministic function of its own inputs on SYNTHETIC data. This validates that the training
pipeline (features -> model -> metrics -> artifacts) works end-to-end and is wired correctly. It is not
evidence the model would perform this well on real patient data, where noise, missing sensors, and label
uncertainty are all worse than in simulation. This caveat must ship with any accuracy number quoted to a
user, per the "no fake/hardcoded values" requirement.

Explainability (SHAP / occlusion) has NOT been built yet — that is ml/explainability, still open.
