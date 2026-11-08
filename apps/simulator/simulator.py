"""Patient sensor simulator: turns scenario physiology into device events, with fault injection.

Emitted event (JSON-serialisable dict):
  {"event_id","patient_id","device_id","seq","timestamp"(ISO-8601 UTC),"kind":"vitals"|"device",
   "vitals":{...,None = sensor disconnected}, "battery":int, "connectivity":"online"|"offline",
   "device_event": "sensor_disconnected"|"sensor_reconnected"|"low_battery" (kind=device)}
event_id = "<device_id>-<seq>" is deterministic, so retries/duplicates are idempotent server-side.
"""
from __future__ import annotations
import random
from datetime import datetime, timezone, timedelta
from .scenarios import get_spec, VitalsGenerator


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class PatientSimulator:
    def __init__(self, patient_id: str, device_id: str, context: dict, scenario: str = "normal",
                 custom: dict | None = None, seed: int = 42, step_minutes: float = 5.0,
                 start_epoch: float | None = None, faults: dict | None = None,
                 offline_windows: list[tuple[int, int]] | None = None):
        self.patient_id, self.device_id, self.context = patient_id, device_id, context
        self.spec = get_spec(scenario, custom)
        self.gen = VitalsGenerator(self.spec, context, seed)
        self.rng = random.Random(seed + 1)
        self.step = step_minutes * 60.0
        self.t0 = start_epoch if start_epoch is not None else datetime.now(timezone.utc).timestamp()
        self.faults = {"malformed_prob": 0.0, "duplicate_prob": 0.0, "delay_prob": 0.0, "delay_ticks": 3,
                       "missing_prob": 0.0, "disconnect": None, **(faults or {})}
        # disconnect example: {"sensor":"spo2","at_tick":40,"duration":6}
        self.offline_windows = offline_windows or []
        self.tick_no, self.seq, self.battery, self._delayed = 0, 0, 100.0, []
        self._disconnected: dict[str, int] = {}
        self._low_batt_sent = False

    def is_offline(self, tick: int | None = None) -> bool:
        k = self.tick_no if tick is None else tick
        return any(a <= k < b for a, b in self.offline_windows)

    def _next_id(self):
        self.seq += 1
        return self.seq, f"{self.device_id}-{self.seq}"

    def tick(self) -> list[dict]:
        """Advance one sample interval; return the events the device emits now."""
        now = self.t0 + self.tick_no * self.step
        t_hours = (self.tick_no * self.step) / 3600.0
        out: list[dict] = []
        vitals, s = self.gen.sample(t_hours, self.faults["missing_prob"])
        d = self.faults["disconnect"]
        if d:
            if self.tick_no == d["at_tick"]:
                self._disconnected[d["sensor"]] = self.tick_no + d["duration"]
                out.append(self._device_event(now, "sensor_disconnected", d["sensor"]))
            for sensor, until in list(self._disconnected.items()):
                if self.tick_no >= until:
                    del self._disconnected[sensor]
                    out.append(self._device_event(now, "sensor_reconnected", sensor))
        for sensor in self._disconnected:
            vitals[sensor] = None
        self.battery = max(0.0, self.battery - self.rng.uniform(0.05, 0.15))
        seq, eid = self._next_id()
        ev = {"event_id": eid, "patient_id": self.patient_id, "device_id": self.device_id, "seq": seq,
              "timestamp": iso(now), "kind": "vitals", "vitals": vitals, "battery": int(self.battery),
              "connectivity": "offline" if self.is_offline() else "online", "_true_severity": round(s, 3)}
        r = self.rng.random()
        if r < self.faults["malformed_prob"]:
            bad = dict(ev); bad["event_id"] = eid + "-bad"
            bad["vitals"] = dict(vitals, spo2=self.rng.choice([-5, 250, "n/a"]))
            out.append(bad)
        elif r < self.faults["malformed_prob"] + self.faults["delay_prob"]:
            self._delayed.append((self.tick_no + self.faults["delay_ticks"], ev))
        else:
            out.append(ev)
            if self.rng.random() < self.faults["duplicate_prob"]:
                out.append(dict(ev))  # exact retransmit, same event_id
        due = [e for (k, e) in self._delayed if k <= self.tick_no]
        self._delayed = [(k, e) for (k, e) in self._delayed if k > self.tick_no]
        out.extend(due)  # arrives late, carries original timestamp
        if self.battery < 20 and not self._low_batt_sent:
            self._low_batt_sent = True
            out.append(self._device_event(now, "low_battery", "gateway"))
        self.tick_no += 1
        return out

    def _device_event(self, now, name, sensor):
        seq, eid = self._next_id()
        return {"event_id": eid, "patient_id": self.patient_id, "device_id": self.device_id, "seq": seq,
                "timestamp": iso(now), "kind": "device", "device_event": name, "sensor": sensor,
                "battery": int(self.battery), "connectivity": "offline" if self.is_offline() else "online"}
