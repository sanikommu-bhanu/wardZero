"""Device adapter abstraction — PROMPT 4 section 3: "Do not create separate logic for simulator data
and real IoT data. Both must enter the SAME ingestion service" — and section 4's MQTT/HTTP transports.

Design: every adapter's only job is turning whatever arrives over its transport into the one shared
event-dict shape apps/api/validation.py and apps/api/pipeline.py already expect (this is exactly
apps/api/simulator_manager.py's existing `flat = {...}` construction and exactly what
`POST /readings` in apps/api/main.py accepts as a JSON body — this module names that existing
agreement explicitly rather than inventing a new one). `DeviceAdapter.emit()` hands the normalized
event straight to `sink` (in the real app, `IngestionPipeline.ingest`) and does not re-validate or
filter first — adding a second validation pass here would itself be exactly the kind of duplicated,
divergent ingestion logic PROMPT 3/4 both forbid. `sink` is where validation, dedup, storage, feature
engineering, risk, and alerting already happen, once, for every transport.

Verification status, per transport:
- SimulatedDeviceAdapter, HttpDeviceAdapter: REAL, TESTED. tests/test_device_adapter.py drives both
  through a real IngestionPipeline + InMemoryRepository end to end and asserts they produce identical
  stored readings for equivalent input — not just that they don't raise.
- MqttDeviceAdapter: STRUCTURAL STUB, BLOCKED. `normalize()` (payload parsing) is real and tested.
  `connect()` raises NotImplementedError — paho-mqtt is not installed in this sandbox and there is no
  network access to install it or to run an Eclipse Mosquitto broker (confirmed the same way every
  other missing dependency in this project was: `pip install paho-mqtt --break-system-packages` fails
  with "No matching distribution found", same as fastapi/sqlalchemy/pytest). See
  docs/integration-audit.md for what running this for real would require.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass
class NormalizedEvent:
    """The one shape every adapter must produce, regardless of transport — exactly what
    apps/api/validation.py's ALLOWED_READING_FIELDS expects and IngestionPipeline.ingest() consumes."""
    payload: dict
    source_protocol: str  # "simulated" | "http" | "mqtt"


class DeviceAdapter(ABC):
    protocol: str

    def __init__(self, sink: Callable[[dict], object]):
        self.sink = sink

    @abstractmethod
    def normalize(self, raw) -> NormalizedEvent:
        """raw: whatever this transport actually delivers (a simulator tick dict, an HTTP JSON body,
        a parsed MQTT payload). Returns the shared event shape; never calls sink or touches storage."""

    def emit(self, raw) -> object:
        event = self.normalize(raw)
        return self.sink(event.payload)


class SimulatedDeviceAdapter(DeviceAdapter):
    """The simulator's per-tick event is already the normalized shape (see
    apps/api/simulator_manager.py) — normalize() here is an identity pass, made explicit so the
    equivalence with HttpDeviceAdapter below is something a test can assert, not just something a
    docstring claims."""
    protocol = "simulated"

    def normalize(self, raw: dict) -> NormalizedEvent:
        return NormalizedEvent(payload=dict(raw), source_protocol="simulated")


class HttpDeviceAdapter(DeviceAdapter):
    """What POST /readings does, expressed as an adapter. A real device — or this sandbox's simulator,
    if pointed at the HTTP route instead of the in-process shortcut SimulatorManager currently uses for
    per-tick performance — posts a JSON body that IS already the normalized shape; HTTP needs no
    transport-specific unwrapping. Real and tested."""
    protocol = "http"

    def normalize(self, raw: dict) -> NormalizedEvent:
        return NormalizedEvent(payload=dict(raw), source_protocol="http")


class MqttDeviceAdapter(DeviceAdapter):
    """** STRUCTURAL STUB — BLOCKED, NOT EXECUTABLE IN THIS SANDBOX. ** See module docstring.

    normalize() converts both MQTT payload shapes PROMPT 4 section 4 specifies:
    - single-sensor: {"patient_id","device_id","sensor_type","value","unit","timestamp","sequence"}
    - multi-vital:   {"patient_id","device_id","timestamp","sequence","vitals": {...}}
    into the shared event shape. That conversion is real and unit-tested without needing a broker.
    connect()/subscribe-and-listen are NOT implemented — writing an unexecuted MQTT client loop would
    be exactly the "looks connected but was never run" code PROMPT 3/4 both explicitly forbid.
    """
    protocol = "mqtt"

    _SENSOR_TYPE_TO_FIELD = {"spo2": "spo2", "heart_rate": "heart_rate", "temperature": "temperature",
                             "respiratory_rate": "resp_rate"}

    def connect(self, broker_host: str = "localhost", broker_port: int = 1883, **kwargs):
        raise NotImplementedError(
            "MQTT broker connectivity is not implemented in this build: paho-mqtt is not installed and "
            "there is no network access in this sandbox to install it or reach a Mosquitto broker. "
            "normalize() (payload parsing) works standalone and is tested — see "
            "tests/test_device_adapter.py — but there is no live subscriber. "
            "See docs/integration-audit.md, 'MQTT ingestion' row.")

    def normalize(self, raw: dict) -> NormalizedEvent:
        if "vitals" in raw:
            vitals = raw["vitals"]
            payload = {
                "event_id": f"{raw.get('device_id', 'unknown')}-{raw.get('sequence', 'noseq')}",
                "patient_id": raw.get("patient_id"), "device_id": raw.get("device_id"),
                "timestamp": raw.get("timestamp"),
                "heart_rate": vitals.get("heart_rate"), "spo2": vitals.get("spo2"),
                "temperature": vitals.get("temperature"), "resp_rate": vitals.get("respiratory_rate"),
                "systolic_bp": vitals.get("systolic_bp"), "diastolic_bp": vitals.get("diastolic_bp"),
            }
        else:
            field = self._SENSOR_TYPE_TO_FIELD.get(raw.get("sensor_type"))
            payload = {
                "event_id": f"{raw.get('device_id', 'unknown')}-{raw.get('sequence', 'noseq')}",
                "patient_id": raw.get("patient_id"), "device_id": raw.get("device_id"),
                "timestamp": raw.get("timestamp"),
            }
            if field:
                payload[field] = raw.get("value")
        return NormalizedEvent(payload=payload, source_protocol="mqtt")
