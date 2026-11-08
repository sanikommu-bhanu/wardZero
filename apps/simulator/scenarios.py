"""Physiological scenario engine.

Model: a latent severity s(t) in [0,1] moves along a smooth curve from s_start to s_end over
`hours_to_peak` simulated hours. Each vital = patient_baseline + s(t) * delta[vital] + noise.
The same engine generates the ML training data, so simulator and model share one physiology.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from ml.features.schema import VITALS, BASELINE, RANGES, NOISE_SD


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    description: str
    deltas: dict
    s_start: float
    s_end: float
    hours_to_peak: float
    hr_irregularity: float = 0.0  # extra HR variance scaled by severity (cardiac stress)


_D = lambda hr, sp, tp, rr, sb, db, ac: dict(zip(VITALS, (hr, sp, tp, rr, sb, db, ac)))
SCENARIOS: dict[str, ScenarioSpec] = {
    "normal": ScenarioSpec("normal", "Stable baseline vitals", _D(0, 0, 0, 0, 0, 0, 0), 0.0, 0.0, 24),
    "fever": ScenarioSpec("fever", "Rising fever with tachycardia", _D(28, -2, 2.2, 5, -6, -3, -15), 0.05, 0.9, 12),
    "breathing_deterioration": ScenarioSpec("breathing_deterioration", "Falling SpO2 with rising respiratory rate",
                                            _D(32, -10, 0.8, 14, 8, 4, -20), 0.05, 1.0, 10),
    "cardiac_stress": ScenarioSpec("cardiac_stress", "Tachycardia, blood-pressure surge, irregular pulse",
                                   _D(45, -3, 0.1, 6, 38, 18, -10), 0.1, 0.95, 8, hr_irregularity=9.0),
    "post_surgery_recovery": ScenarioSpec("post_surgery_recovery", "Elevated early post-op vitals recovering over time",
                                          _D(25, -4, 1.4, 6, -10, -4, -25), 0.6, 0.1, 24),
}


def custom_spec(deltas: dict, s_start=0.0, s_end=1.0, hours_to_peak=8.0, name="custom") -> ScenarioSpec:
    bad = set(deltas) - set(VITALS)
    if bad:
        raise ValueError(f"unknown vitals in custom scenario: {sorted(bad)}")
    if not (0 <= s_start <= 1 and 0 <= s_end <= 1) or hours_to_peak <= 0:
        raise ValueError("s_start/s_end must be in [0,1] and hours_to_peak > 0")
    full = {v: float(deltas.get(v, 0.0)) for v in VITALS}
    return ScenarioSpec(name, "User-defined scenario", full, s_start, s_end, hours_to_peak)


def get_spec(name: str, custom: dict | None = None) -> ScenarioSpec:
    if name == "custom":
        return custom_spec(**(custom or {}))
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario '{name}'. Options: {sorted(SCENARIOS)+['custom']}")
    return SCENARIOS[name]


def _smooth(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def severity_at(spec: ScenarioSpec, t_hours: float) -> float:
    return spec.s_start + (spec.s_end - spec.s_start) * _smooth(t_hours / spec.hours_to_peak)


def patient_baseline(ctx: dict) -> dict:
    b = dict(BASELINE)
    if ctx.get("hypertension"):
        b["systolic_bp"] += 14; b["diastolic_bp"] += 6
    if ctx.get("copd"):
        b["spo2"] -= 2.0; b["resp_rate"] += 1.5
    if ctx.get("cardiac"):
        b["heart_rate"] += 3
    if ctx.get("age", 0) >= 75:
        b["activity"] -= 6
    return b


class VitalsGenerator:
    def __init__(self, spec: ScenarioSpec, context: dict, seed: int = 0):
        self.spec, self.base, self.rng = spec, patient_baseline(context), random.Random(seed)

    def sample(self, t_hours: float, missing_prob: float = 0.0) -> tuple[dict, float]:
        s = severity_at(self.spec, t_hours)
        out = {}
        for v in VITALS:
            sd = NOISE_SD[v]
            if v == "heart_rate":
                sd += self.spec.hr_irregularity * s
            val = self.base[v] + s * self.spec.deltas[v] + self.rng.gauss(0, sd)
            lo, hi = RANGES[v]
            val = min(max(val, lo), hi)
            if v == "spo2":
                val = min(val, 100.0)
            out[v] = None if self.rng.random() < missing_prob else (round(val) if v in ("heart_rate", "resp_rate", "systolic_bp", "diastolic_bp", "activity") else round(val, 1 if v == "spo2" else 2))
        return out, s
