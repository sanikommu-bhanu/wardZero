"""Feature engineering: readings window + patient context + note signals -> flat feature dict."""
from __future__ import annotations
import numpy as np
from .schema import VITALS, BASELINE, CONTEXT_KEYS, NOTE_KEYS, WINDOW

_STATS = ("last", "mean", "std", "slope_h", "delta")
FEATURE_NAMES = (
    [f"{v}_{s}" for v in VITALS for s in _STATS]
    + ["spo2_min", "temperature_max", "heart_rate_max", "resp_rate_max", "shock_index",
       "pulse_pressure", "n_abnormal", "window_hours"]
    + list(CONTEXT_KEYS) + ["comorbidity_count"]
    + [f"note_{k}" for k in NOTE_KEYS] + ["note_signal_count"]
)


def _abnormal_count(last: dict) -> int:
    c = 0
    c += last["heart_rate"] > 100 or last["heart_rate"] < 50
    c += last["spo2"] < 94
    c += last["temperature"] >= 38.0 or last["temperature"] < 36.0
    c += last["resp_rate"] >= 22 or last["resp_rate"] <= 10
    c += last["systolic_bp"] < 100 or last["systolic_bp"] >= 160
    return int(c)


def build_features(readings: list[dict], context: dict, note_signals: dict | None = None):
    """readings: chronological list of {'t': epoch_seconds, <vital>: float|None}.
    Returns (features, quality). Missing sensors are forward-filled, then baseline-filled;
    this is reported in `quality` (never silently hidden)."""
    rs = sorted(readings, key=lambda r: r["t"])[-WINDOW:]
    quality = {"n_readings": len(rs), "missing_sensors": [], "insufficient_history": len(rs) < 3}
    feats: dict[str, float] = {}
    t = np.array([r["t"] for r in rs], dtype=float) if rs else np.array([0.0])
    span_h = float((t[-1] - t[0]) / 3600.0) if len(t) > 1 else 0.0
    last_vals = {}
    for v in VITALS:
        y = np.array([np.nan if r.get(v) is None else float(r[v]) for r in rs], dtype=float) if rs else np.array([np.nan])
        ok = ~np.isnan(y)
        if not ok.any():
            quality["missing_sensors"].append(v)
            y_ok, t_ok = np.array([BASELINE[v]]), np.array([t[-1]])
        else:
            y_ok, t_ok = y[ok], t[ok]
            if not ok[-1]:
                quality["missing_sensors"].append(v)  # latest sample missing -> carried forward
        last_vals[v] = float(y_ok[-1])
        slope = 0.0
        if len(y_ok) >= 3 and (t_ok[-1] - t_ok[0]) > 0:
            slope = float(np.polyfit((t_ok - t_ok[0]) / 3600.0, y_ok, 1)[0])
        feats[f"{v}_last"] = last_vals[v]
        feats[f"{v}_mean"] = float(y_ok.mean())
        feats[f"{v}_std"] = float(y_ok.std())
        feats[f"{v}_slope_h"] = slope
        feats[f"{v}_delta"] = float(y_ok[-1] - y_ok[0])

    def col(v):
        a = np.array([r[v] for r in rs if r.get(v) is not None], dtype=float)
        return a if a.size else np.array([BASELINE[v]])
    feats["spo2_min"] = float(col("spo2").min())
    feats["temperature_max"] = float(col("temperature").max())
    feats["heart_rate_max"] = float(col("heart_rate").max())
    feats["resp_rate_max"] = float(col("resp_rate").max())
    feats["shock_index"] = last_vals["heart_rate"] / max(last_vals["systolic_bp"], 1.0)
    feats["pulse_pressure"] = last_vals["systolic_bp"] - last_vals["diastolic_bp"]
    feats["n_abnormal"] = float(_abnormal_count(last_vals))
    feats["window_hours"] = span_h
    for k in CONTEXT_KEYS:
        feats[k] = float(context.get(k, 0) or 0)
    feats["comorbidity_count"] = float(sum(bool(context.get(k)) for k in ("hypertension", "diabetes", "cardiac", "copd")))
    ns = note_signals or {}
    for k in NOTE_KEYS:
        feats[f"note_{k}"] = 1.0 if ns.get(k) else 0.0
    feats["note_signal_count"] = float(sum(feats[f"note_{k}"] for k in NOTE_KEYS))
    return feats, quality


def to_vector(feats: dict) -> np.ndarray:
    return np.array([feats[n] for n in FEATURE_NAMES], dtype=float)
