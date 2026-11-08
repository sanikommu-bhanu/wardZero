# Synthetic held-out evaluation: ML risk vs NEWS2 baseline

> **SYNTHETIC DATA. Not clinical validation.** Train and test share one generator, so numbers are optimistic.

Test patients: 45 (27 reach HIGH severity, 18 never do); rows: 8865.

## Discrimination (deteriorates within 24 h)
| Score | ROC-AUC | PR-AUC | prevalence |
|---|---|---|---|
| ml | 0.964 | 0.963 | 0.482 |
| news2 | 0.782 | 0.791 | 0.482 |

## Calibration (ML)  Brier 0.0815 (constant-prevalence reference 0.2497), ECE 0.086
| bin | n | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 1406 | 0.05 | 0.00 |
| 0.1-0.2 | 928 | 0.15 | 0.00 |
| 0.2-0.3 | 334 | 0.24 | 0.07 |
| 0.3-0.4 | 870 | 0.36 | 0.55 |
| 0.4-0.5 | 470 | 0.44 | 0.51 |
| 0.5-0.6 | 251 | 0.55 | 0.44 |
| 0.6-0.7 | 294 | 0.64 | 0.79 |
| 0.7-0.8 | 66 | 0.75 | 0.98 |
| 0.8-0.9 | 81 | 0.85 | 1.00 |
| 0.9-1.0 | 2005 | 0.99 | 1.00 |

## Fixed alarm budget (thresholds fitted on validation patients, 6 h refractory, true alarm = within 48 h before event)
| budget /pt/day | score | realised alarms /pt/day | false alarms /pt/day | sensitivity | median lead (h) |
|---|---|---|---|---|---|
| 0.5 | ml | 0.48 | 0.01 | 1.00 | 15.0 |
| 0.5 | news2 | 0.40 | 0.13 | 0.89 | 2.5 |
| 1.0 | ml | 1.09 | 0.19 | 1.00 | 25.5 |
| 1.0 | news2 | 0.40 | 0.13 | 0.89 | 2.5 |
| 2.0 | ml | 1.36 | 0.24 | 1.00 | 33.5 |
| 2.0 | news2 | 1.08 | 0.64 | 1.00 | 3.5 |
| 4.0 | ml | 1.36 | 0.24 | 1.00 | 33.5 |
| 4.0 | news2 | 1.08 | 0.64 | 1.00 | 3.5 |

## NEWS2 at standard thresholds
| rule | alarms /pt/day | false alarms /pt/day | sensitivity | median lead (h) |
|---|---|---|---|---|
| NEWS2 >=3 | 0.24 | 0.07 | 0.59 | 2.8 |
| NEWS2 >=5 | 0.09 | 0.00 | 0.37 | 1.8 |
| NEWS2 >=7 | 0.06 | 0.00 | 0.26 | 1.0 |
