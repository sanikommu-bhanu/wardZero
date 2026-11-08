# Step 2 — ml/data/generator.py — VERIFIED

Command: `PYTHONPATH=. python3 -m unittest tests.test_data_generator -v` -> 14/14 pass.
Command: `PYTHONPATH=. python3 ml/data/generator.py --patients-per-scenario 60 --steps 200 --out ml/data/synthetic_dataset.csv`
(parquet libs (pyarrow/fastparquet) are not installed in this sandbox and cannot be fetched (no network),
so the generator's own fallback writes CSV instead -- this fallback path was exercised for real, not assumed).

Labels come from the simulator's own latent severity curve (apps.simulator.scenarios.severity_at), not from
the vitals themselves, so features and labels are not circularly defined by construction.
Splits are by patient_id (group_split), verified by test_no_patient_in_two_splits.

Known limitation, stated rather than hidden: with 200 steps at 15-minute resolution (~50 simulated hours),
the 48h-ahead deterioration label has very few positive examples for scenarios that peak early
(breathing_deterioration peaks by ~10h, cardiac_stress by ~8h) -- by 48h out most trajectories have already
plateaued rather than newly deteriorated. Positive rate for deteriorates_48h is ~0.6% in this run (see
evidence/metrics.json). That is a real class-imbalance problem carried into Step 3, not a bug to paper over.
