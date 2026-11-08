"""STEP 12 (this session) — bridges apps/simulator/simulator.PatientSimulator (already written and
unit-tested — see tests/test_data_generator.py's use of the same scenario engine, and STATUS.md item 0)
to the live API so the frontend's IoT Simulator screen controls a *real* running simulation, not a
decorative animation.

** VERIFICATION STATUS: WRITTEN, NOT EXECUTED. ** Same reason as the rest of apps/api/: fastapi/uvicorn
are not installed in this sandbox and there is no network access to install them. The pure-Python parts
(flatten_vitals_event, _patient_context_from_profile) have no fastapi/asyncio dependency and are unit
tested in tests/test_simulator_manager.py; the asyncio scheduling loop itself has not been run under a
real event loop here.

Design: one PatientSimulator per patient_id, ticked on an asyncio task at
`step_minutes-of-sim-time / speed` wall-clock seconds per tick (speed 1x/2x/5x). Every tick's vitals
event is flattened and passed through the *existing* IngestionPipeline.ingest(...) — the same code path
apps/api/main.py's POST /readings uses — so risk assessment, alerting and timeline population are
identical whether a reading comes from the simulator or a real POST. Device (dis)connect events update
apps/api/repository.InMemoryRepository's new device-state store and are broadcast separately.
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field

from apps.simulator.simulator import PatientSimulator
from apps.simulator.scenarios import SCENARIOS


def flatten_vitals_event(ev: dict, scenario: str) -> dict:
    """A simulator 'kind':'vitals' event nests vitals under ev['vitals']; the ingestion pipeline's
    validate_event expects them at the top level (see apps/api/validation.ALLOWED_READING_FIELDS).
    This is a pure data-reshaping function with no side effects, so it's cheap to unit test without
    fastapi/asyncio installed."""
    flat = {
        "event_id": ev["event_id"], "patient_id": ev["patient_id"], "device_id": ev["device_id"],
        "timestamp": ev["timestamp"], "connectivity": ev.get("connectivity", "online"),
        "scenario": scenario,
    }
    vitals = ev.get("vitals") or {}
    for k, v in vitals.items():
        flat[k] = v
    return flat


def patient_context_from_profile(profile: dict) -> dict:
    """profile: the dict shape returned by frontend_routes._profile_dict. Kept deliberately tiny —
    ml.features.engineering.build_features only reads the comorbidity flags it recognizes and ignores
    anything else, so passing extra keys is harmless."""
    return {
        "age": profile.get("age") if profile.get("age") is not None else 60,  # None would crash the generator
        "hypertension": bool(profile.get("hypertension")),
        "diabetes": bool(profile.get("diabetes")),
        "cardiac": bool(profile.get("cardiac")),
        "copd": bool(profile.get("copd")),
        "post_surgery": bool(profile.get("post_surgery")),
    }


@dataclass
class SimRun:
    patient_id: str
    device_id: str
    scenario: str
    speed: float
    sim: PatientSimulator
    task: object = None
    context: dict = field(default_factory=dict)  # patient context used for every ingested tick
    status: str = "running"  # running | paused | stopped
    tick_count: int = 0
    event_log: list = field(default_factory=list)  # last N flattened events, newest last

    def snapshot(self) -> dict:
        return {
            "patient_id": self.patient_id, "device_id": self.device_id, "scenario": self.scenario,
            "speed": self.speed, "status": self.status, "tick_count": self.tick_count,
            "recent_events": self.event_log[-20:],
        }


class SimulatorManager:
    """Process-local, like InMemoryRepository/AlertStore in main.py — a real SQL-backed job queue
    (e.g. a proper task runner) is the persistence upgrade path noted in STATUS.md for a production
    deployment; for this prototype one process's simulators are all there are, matching how the rest
    of apps/api/ is wired for this stage of the project."""

    def __init__(self, pipeline, repo, ws_manager, step_minutes: float = 5.0):
        self.pipeline = pipeline
        self.repo = repo
        self.ws = ws_manager
        self.step_minutes = step_minutes
        self.runs: dict[str, SimRun] = {}
        self._event_loop = None

    def bind_loop(self, loop):
        """Remember the server's event loop: start()/pause() are called from FastAPI's threadpool
        (plain `def` routes), where asyncio.ensure_future() has no running loop and would fail."""
        self._event_loop = loop

    def _spawn(self, run):
        try:
            asyncio.get_running_loop()
            return asyncio.ensure_future(self._loop(run))
        except RuntimeError:
            if self._event_loop is None or not self._event_loop.is_running():
                raise RuntimeError("SimulatorManager has no running event loop bound (call bind_loop at startup)")
            return asyncio.run_coroutine_threadsafe(self._loop(run), self._event_loop)

    def available_scenarios(self) -> list[dict]:
        return [{"name": s.name, "description": s.description} for s in SCENARIOS.values()] + [
            {"name": "custom", "description": "Custom vital-sign deltas supplied by the caller"}]

    def status(self, patient_id: str | None = None):
        if patient_id:
            run = self.runs.get(patient_id)
            return run.snapshot() if run else None
        return [r.snapshot() for r in self.runs.values()]

    def start(self, patient_id: str, device_id: str, patient_profile: dict, scenario: str = "normal",
             speed: float = 1.0, custom: dict | None = None) -> dict:
        existing = self.runs.get(patient_id)
        if existing and existing.status == "running":
            return existing.snapshot()
        if existing and existing.status == "paused" and existing.scenario == scenario:
            existing.status = "running"
            existing.speed = speed
            existing.task = self._spawn(existing)
            return existing.snapshot()

        context = patient_context_from_profile(patient_profile)
        sim = PatientSimulator(patient_id=patient_id, device_id=device_id, context=context,
                               scenario=scenario, custom=custom, step_minutes=self.step_minutes,
                               start_epoch=time.time())
        run = SimRun(patient_id=patient_id, device_id=device_id, scenario=scenario, speed=speed, sim=sim,
                     context=context)
        self.runs[patient_id] = run
        run.task = self._spawn(run)
        return run.snapshot()

    def pause(self, patient_id: str) -> dict | None:
        run = self.runs.get(patient_id)
        if not run:
            return None
        run.status = "paused"
        if run.task:
            run.task.cancel()
        return run.snapshot()

    def stop(self, patient_id: str) -> dict | None:
        run = self.runs.get(patient_id)
        if not run:
            return None
        run.status = "stopped"
        if run.task:
            run.task.cancel()
        del self.runs[patient_id]
        return run.snapshot()

    def reset(self, patient_id: str, device_id: str, patient_profile: dict, scenario: str = "normal",
             speed: float = 1.0, custom: dict | None = None) -> dict:
        self.stop(patient_id)
        return self.start(patient_id, device_id, patient_profile, scenario, speed, custom)

    async def _loop(self, run: SimRun):
        try:
            while run.status == "running":
                wall_seconds = max(0.25, (self.step_minutes * 60.0) / max(run.speed, 0.1) / 60.0)
                # Compressed for a live demo: 5 sim-minutes of physiology per `wall_seconds` real
                # seconds (divided again by ~60 above so "1x" is watchable rather than a 5-minute wait).
                await asyncio.sleep(wall_seconds)
                events = run.sim.tick()
                run.tick_count += 1
                for ev in events:
                    if ev.get("kind") == "vitals":
                        flat = flatten_vitals_event(ev, run.scenario)
                        result = self.pipeline.ingest(flat, run.context)
                        self.repo.set_device_state(run.device_id, ev.get("connectivity", "online"),
                                                   ev.get("battery"))
                        payload = {"type": "sim_reading", "patient_id": run.patient_id,
                                  "device_id": run.device_id, "reading": flat,
                                  "battery": ev.get("battery"), "connectivity": ev.get("connectivity"),
                                  "risk_assessment": result.risk_assessment,
                                  "status": result.status}
                        run.event_log.append(payload)
                        self.ws.broadcast_sync(payload)
                        if result.notification:
                            self.ws.broadcast_sync(result.notification)
                    elif ev.get("kind") == "device":
                        self.repo.store_device_event(run.device_id, ev)
                        self.repo.set_device_state(run.device_id, ev.get("connectivity", "online"),
                                                   ev.get("battery"))
                        payload = {"type": "device_event", "patient_id": run.patient_id,
                                  "device_id": run.device_id, "event": ev}
                        run.event_log.append(payload)
                        self.ws.broadcast_sync(payload)
        except asyncio.CancelledError:
            return
