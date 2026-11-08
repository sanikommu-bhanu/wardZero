# Model card: WardZero deterioration-risk model

**Status: research prototype. Not clinically validated. Not a medical device. Decision support only.**

## Intended use
Rank synthetic home-care patients by short-term deterioration risk and explain why, next to the published NEWS2 score.
Not for diagnosis, triage of real patients, or replacing clinical judgement or emergency services.

## Model
scikit-learn classifiers (risk class; deteriorates within 24 h; within 48 h) on rolling-window features of heart rate,
SpO2, temperature, respiratory rate, blood pressure and activity, plus patient context and note-derived signals
(`ml/features`). Explanations: SHAP when installed, otherwise occlusion attribution. A rules engine and unconditional
hard thresholds back the model up; the AI abstains when there are too few readings.

## Data
100% synthetic, from the same physiology engine that drives the simulator. Patients (not rows) are split into
train/val/test. No real patient data was used for training or evaluation.

## Results (synthetic test set, 45 patients, `evidence/eval_synthetic.md`, reproduce: `python -m ml.evaluation.run_eval`)
| | ROC-AUC | PR-AUC |
|---|---|---|
| ML, deteriorates within 24 h | 0.964 | 0.963 |
| NEWS2 on the same rows | 0.782 | 0.791 |

At a fixed budget of about 1 alarm/patient/day (thresholds fitted on validation patients): ML sensitivity 1.00, median
lead 25.5 h, 0.19 false alarms/patient/day; NEWS2 sensitivity 0.89, median lead 2.5 h. NEWS2 at the standard >=5 and >=7
cut-offs has sensitivity 0.37 and 0.26.

**Read these with care.** Train and test share one generator, so the gap over NEWS2 partly reflects that the labels come
from the same latent severity the ML features track; it will not transfer to real patients. The test set is small.
Calibration is imperfect (ECE 0.086; the 0.1-0.3 bins predict 15-24% but observe about 0-7%, the 0.3-0.4 bin under-predicts).
The 48 h model's positive class is very rare in some splits, so its metrics are unreliable. The risk-class accuracy
reflects an easy synthetic labelling rule.

## Real data
`ml/data/physionet.py` and `ml/evaluation/real_data_check.py` can score the NEWS2 baseline on PhysioNet/CinC 2019
sepsis-format files. They are unit-tested on a tiny synthetic fixture only and have never been run on the real dataset.
The ML model is deliberately NOT applied to real data: it was trained on synthetic data and doing so would be unvalidated.

## Known limitations
- NEWS2 omits supplemental oxygen and consciousness (assumed air / Alert) because the system does not measure them.
- Hindi, Tamil and Telugu note lexicons have not been reviewed by native-speaking clinicians.
- Sensor simulators only; no real hardware. No MQTT broker was available to test.
- Not evaluated for fairness across age, sex, or comorbidity subgroups.
- Needed before any clinical use: prospective, external validation on real data; clinician review; regulatory assessment.
