"""NEWS2 (Royal College of Physicians, 2017) — a transparent, published early-warning score used here as the
BASELINE shown next to the ML risk estimate. Fully deterministic: every point is traceable to one vital.

Inputs available in this system: respiratory rate, SpO2, systolic BP, pulse, temperature. NOT available:
supplemental-oxygen flag and ACVPU consciousness level. Defaults are explicit assumptions and are returned in
`assumptions` so the UI can show them: breathing air (0 pts), Alert (0 pts) unless a caregiver note reports new
confusion (-> 3 pts). SpO2 Scale 2 (target 88-92%) is used only if the patient has COPD AND `use_scale2` is
confirmed in the context; otherwise Scale 1 — a clinician must make that call, so the default is Scale 1.
NEWS2 is a decision-support score, not a diagnosis. Thresholds reproduced from the published chart; verify
against the current RCP document before any real-world use.
"""
from __future__ import annotations


def _band(v, table):
    for lo, hi, pts in table:
        if (lo is None or v >= lo) and (hi is None or v <= hi):
            return pts
    return 0


RR = [(None, 8, 3), (9, 11, 1), (12, 20, 0), (21, 24, 2), (25, None, 3)]
SPO2_S1 = [(None, 91, 3), (92, 93, 2), (94, 95, 1), (96, None, 0)]
SPO2_S2_AIR = [(None, 83, 3), (84, 85, 2), (86, 87, 1), (88, None, 0)]
SBP = [(None, 90, 3), (91, 100, 2), (101, 110, 1), (111, 219, 0), (220, None, 3)]
PULSE = [(None, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1), (111, 130, 2), (131, None, 3)]
TEMP = [(None, 35.0, 3), (35.1, 36.0, 1), (36.1, 38.0, 0), (38.1, 39.0, 1), (39.1, None, 2)]

RESPONSE = {
    "low": "Ward-based response: minimum 4-12 hourly observations (clinical team to set frequency).",
    "low_medium": "A single parameter scores 3: urgent ward-based review by a clinician.",
    "medium": "Urgent response: clinician review, consider critical-care outreach.",
    "high": "Emergency response: immediate clinical review / emergency services.",
}


def news2(reading: dict, *, on_oxygen: bool = False, new_confusion: bool = False, use_scale2: bool = False) -> dict:
    params, missing = [], []

    def add(name, key, table, unit, value=None):
        v = reading.get(key) if value is None else value
        if v is None:
            missing.append(name)
            return
        params.append({"name": name, "value": v, "unit": unit, "points": _band(v, table)})

    add("Respiratory rate", "resp_rate", RR, "/min")
    spo2 = reading.get("spo2")
    if spo2 is None:
        missing.append("SpO2")
    else:
        if use_scale2:
            pts = _band(spo2, SPO2_S2_AIR) if not on_oxygen else (
                3 if spo2 >= 97 else 2 if spo2 >= 95 else 1 if spo2 >= 93 else 0 if spo2 >= 88 else _band(spo2, SPO2_S2_AIR))
        else:
            pts = _band(spo2, SPO2_S1)
        params.append({"name": "SpO2 (Scale 2)" if use_scale2 else "SpO2 (Scale 1)", "value": spo2, "unit": "%", "points": pts})
    params.append({"name": "Air or oxygen", "value": "oxygen" if on_oxygen else "air (assumed)", "unit": "", "points": 2 if on_oxygen else 0})
    add("Systolic BP", "systolic_bp", SBP, "mmHg")
    add("Pulse", "heart_rate", PULSE, "bpm")
    params.append({"name": "Consciousness", "value": "new confusion (from caregiver note)" if new_confusion else "Alert (assumed)",
                   "unit": "", "points": 3 if new_confusion else 0})
    add("Temperature", "temperature", TEMP, "°C")

    total = sum(p["points"] for p in params)
    any3 = any(p["points"] == 3 for p in params)
    if total >= 7:
        band = "high"
    elif total >= 5:
        band = "medium"
    elif any3:
        band = "low_medium"
    else:
        band = "low"
    assumptions = ["No supplemental-oxygen data: " + ("oxygen flag supplied" if on_oxygen else "assumed breathing air"),
                   "No ACVPU data: " + ("new confusion taken from caregiver note" if new_confusion else "assumed Alert"),
                   "SpO2 Scale 2 (COPD target 88-92%) " + ("applied" if use_scale2 else "not applied; clinician must decide")]
    return {"score": total, "band": band, "response": RESPONSE[band], "parameters": params,
            "missing_parameters": missing, "complete": not missing, "assumptions": assumptions,
            "source": "NEWS2, Royal College of Physicians 2017 (baseline, not validated here)"}


def escalation_from_news2(n: dict) -> str:
    """Conservative mapping used ONLY to raise (never lower) the ML escalation."""
    return {"high": "emergency", "medium": "escalate_to_doctor", "low_medium": "caregiver_review"}.get(n["band"], "routine_monitoring")
