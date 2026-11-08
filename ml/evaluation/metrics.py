"""Evaluation metrics: discrimination, calibration, and alarm-burden / lead-time metrics for early-warning scores.
All functions are pure and take plain arrays so they work identically on synthetic and real data."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def discrimination(y, score) -> dict:
    y, score = np.asarray(y), np.asarray(score, dtype=float)
    if len(set(y.tolist())) < 2:
        return {"roc_auc": None, "pr_auc": None, "prevalence": float(y.mean()) if len(y) else None, "n": int(len(y))}
    return {"roc_auc": float(roc_auc_score(y, score)), "pr_auc": float(average_precision_score(y, score)),
            "prevalence": float(y.mean()), "n": int(len(y))}


def calibration(y, prob, n_bins: int = 10) -> dict:
    """Reliability table (equal-width bins), Brier score, expected calibration error. `prob` must be probabilities."""
    y, prob = np.asarray(y, dtype=float), np.asarray(prob, dtype=float)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(prob, edges[1:-1]), 0, n_bins - 1)
    bins, ece = [], 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        conf, acc, n = float(prob[m].mean()), float(y[m].mean()), int(m.sum())
        ece += n / len(y) * abs(conf - acc)
        bins.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "n": n, "mean_predicted": conf, "observed_rate": acc})
    base = float(y.mean())
    return {"brier": float(brier_score_loss(y, prob)), "brier_reference_constant_prevalence": base * (1 - base),
            "ece": float(ece), "bins": bins}


def alarm_times(times_h, scores, threshold: float, refractory_h: float, stop_h: float | None = None) -> list[float]:
    """Alarm whenever score >= threshold, then silent for `refractory_h` (alarm-fatigue control). Optionally stop at stop_h."""
    out, last = [], -1e18
    for t, s in zip(times_h, scores):
        if stop_h is not None and t >= stop_h:
            break
        if s >= threshold and t - last >= refractory_h:
            out.append(float(t))
            last = t
    return out


def evaluate_policy(patients: list[dict], threshold: float, refractory_h: float = 6.0, lookback_h: float = 48.0) -> dict:
    """patients: [{times_h, scores, event_h|None}]. Events = patients with event_h. An alarm is TRUE if it lands within
    `lookback_h` before the event; every other alarm (controls, or >lookback_h before an event) is FALSE. Post-event time
    is not monitored (already deteriorated). Reports sensitivity (event patients with >=1 true alarm), lead times, and
    alarms / false alarms per patient per day."""
    n_event = n_detected = 0
    leads, total_alarms, false_alarms, monitored_h = [], 0, 0, 0.0
    for p in patients:
        t = np.asarray(p["times_h"], dtype=float)
        if len(t) == 0:
            continue
        ev = p.get("event_h")
        end = ev if ev is not None else float(t[-1])
        monitored_h += max(0.0, end - float(t[0]))
        alarms = alarm_times(t, p["scores"], threshold, refractory_h, stop_h=ev)
        total_alarms += len(alarms)
        if ev is None:
            false_alarms += len(alarms)
            continue
        n_event += 1
        true = [a for a in alarms if ev - lookback_h <= a < ev]
        false_alarms += len(alarms) - len(true)
        if true:
            n_detected += 1
            leads.append(ev - true[0])
    days = max(monitored_h / 24.0, 1e-9)
    return {"threshold": float(threshold), "event_patients": n_event, "detected": n_detected,
            "sensitivity": (n_detected / n_event) if n_event else None,
            "median_lead_time_h": float(np.median(leads)) if leads else None,
            "alarms_per_patient_day": total_alarms / days,          # `days` = total monitored patient-days
            "false_alarms_per_patient_day": false_alarms / days,
            "monitored_patient_days": days}


def threshold_for_alarm_budget(patients: list[dict], target_per_patient_day: float, refractory_h: float = 6.0,
                               candidates=None) -> float:
    """Pick the LOWEST threshold whose alarms/patient/day does not exceed the budget. Fit this on a VALIDATION split."""
    all_scores = np.concatenate([np.asarray(p["scores"], dtype=float) for p in patients])
    cands = sorted(set(candidates if candidates is not None else np.unique(np.quantile(all_scores, np.linspace(0.5, 0.999, 120)))))
    best = float(np.nextafter(max(cands[-1], float(all_scores.max())), np.inf))  # above every score: zero alarms if budget unreachable
    for thr in cands:   # ascending threshold -> descending alarm rate
        r = evaluate_policy(patients, thr, refractory_h)
        if r["alarms_per_patient_day"] <= target_per_patient_day:
            return float(thr)
    return float(best)
