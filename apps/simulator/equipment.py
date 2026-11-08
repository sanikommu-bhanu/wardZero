"""Home-care equipment simulators with injectable faults: oxygen concentrator and IV/infusion pump.
Software only — no real device is connected. Alarm limits are demo defaults, NOT device specifications."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

# fault -> (severity label used by the alert engine, human text)
FAULTS = {
    "power_failure": ("emergency", "Mains power lost - running on backup"),
    "low_purity": ("escalate_to_doctor", "Oxygen purity below alarm limit"),
    "low_flow": ("escalate_to_doctor", "Oxygen flow below prescribed rate"),
    "high_temperature": ("caregiver_review", "Concentrator over-temperature"),
    "occlusion": ("escalate_to_doctor", "Infusion line occlusion"),
    "air_in_line": ("emergency", "Air detected in infusion line"),
    "empty": ("escalate_to_doctor", "Infusion container empty"),
    "battery_low": ("caregiver_review", "Pump battery low"),
}


@dataclass
class EquipmentEvent:
    device_id: str
    device_type: str
    fault: str
    active: bool
    recommended_escalation: str
    message: str
    value: float | None = None

    def to_dict(self):
        return self.__dict__.copy()


@dataclass
class OxygenConcentrator:
    device_id: str
    prescribed_lpm: float = 2.0
    purity_alarm_pct: float = 85.0
    mains: bool = True
    flow_lpm: float = 2.0
    purity_pct: float = 93.0
    temp_c: float = 38.0
    _faults: set = field(default_factory=set)
    device_type: str = "oxygen_concentrator"

    def inject(self, fault: str):
        self._faults.add(fault)

    def clear(self, fault: str):
        self._faults.discard(fault)

    def tick(self, rng: random.Random | None = None) -> list[EquipmentEvent]:
        rng = rng or random.Random()
        self.mains = "power_failure" not in self._faults
        self.purity_pct = (78.0 if "low_purity" in self._faults else 93.0) + rng.uniform(-0.5, 0.5)
        self.flow_lpm = (0.8 if "low_flow" in self._faults else self.prescribed_lpm) + rng.uniform(-0.05, 0.05)
        if not self.mains:
            self.flow_lpm = 0.0
        self.temp_c = (52.0 if "high_temperature" in self._faults else 38.0) + rng.uniform(-0.3, 0.3)
        state = {"power_failure": not self.mains, "low_purity": self.purity_pct < self.purity_alarm_pct,
                 "low_flow": self.mains and self.flow_lpm < 0.8 * self.prescribed_lpm, "high_temperature": self.temp_c > 45.0}
        val = {"power_failure": None, "low_purity": self.purity_pct, "low_flow": self.flow_lpm, "high_temperature": self.temp_c}
        return [EquipmentEvent(self.device_id, self.device_type, f, on, FAULTS[f][0], FAULTS[f][1], val[f]) for f, on in state.items() if on]


@dataclass
class IvPump:
    device_id: str
    rate_ml_h: float = 100.0
    volume_ml: float = 500.0
    battery_pct: float = 100.0
    _faults: set = field(default_factory=set)
    device_type: str = "iv_pump"

    def inject(self, fault: str):
        self._faults.add(fault)

    def clear(self, fault: str):
        self._faults.discard(fault)

    def tick(self, minutes: float = 5.0) -> list[EquipmentEvent]:
        blocked = {"occlusion", "air_in_line"} & self._faults
        if not blocked and self.volume_ml > 0:
            self.volume_ml = max(0.0, self.volume_ml - self.rate_ml_h * minutes / 60.0)
        self.battery_pct = max(0.0, self.battery_pct - (6.0 if "battery_low" in self._faults else 0.05) * minutes / 5.0)
        out = []
        for f in ("occlusion", "air_in_line"):
            if f in self._faults:
                out.append(EquipmentEvent(self.device_id, self.device_type, f, True, FAULTS[f][0], FAULTS[f][1]))
        if self.volume_ml <= 0:
            out.append(EquipmentEvent(self.device_id, self.device_type, "empty", True, FAULTS["empty"][0], FAULTS["empty"][1], 0.0))
        if self.battery_pct < 20:
            out.append(EquipmentEvent(self.device_id, self.device_type, "battery_low", True, FAULTS["battery_low"][0],
                                      FAULTS["battery_low"][1], self.battery_pct))
        return out


def equipment_alert(alert_store, patient_id: str, ev: EquipmentEvent):
    """Turn an active equipment fault into an alert through the SAME alert engine (dedup, lifecycle, ladder)."""
    assessment = {"risk_level": "EQUIPMENT", "probability": 1.0, "recommended_escalation": ev.recommended_escalation,
                  "hard_threshold_breaches": [], "explanation": f"{ev.device_type} {ev.device_id}: {ev.message}",
                  "contributing_factors": [{"feature": ev.fault, "value": ev.value, "direction": "increases_risk"}],
                  "method": "equipment", "forecast": {}, "trend": {}, "disclaimer": "Simulated equipment fault."}
    return alert_store.detect(patient_id, f"equipment_{ev.device_type}_{ev.fault}", assessment)
