"""STEP 8/10/11 — FastAPI app: thin HTTP/WebSocket wrapper around the already-tested,
framework-independent logic in apps/api/pipeline.py, apps/api/auth.py and services/alert_engine.

** VERIFICATION STATUS: exercised against STAND-INS for fastapi/pydantic/sqlalchemy, NOT against the real
packages. ** `python3 tools/offline_smoke/run_smoke.py` imports this module with tiny fastapi/pydantic stubs and a
fake SQLAlchemy layer and drives the auth, ingestion, batch-replay, alert-lifecycle, equipment, check-in, notes,
simulator and WebSocket code paths with real JWTs, the real pipeline, SQLite repository and alert store (28
assertions; it found and fixed real bugs). What it cannot cover: FastAPI's own routing/validation (422s), CORS,
real Starlette WebSockets and every SQLAlchemy-backed route (/patients, /devices, /caregivers, /analytics,
/reports, simulator start's patient lookup). Treat those as reviewed-but-unexecuted until uvicorn has run.

Run (once fastapi/uvicorn are installed, e.g. on a machine with network access):
    uvicorn apps.api.main:app --reload
"""
from __future__ import annotations
import asyncio
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database.session import get_session, init_db
from database.models import User, RoleEnum, Patient, PatientProfile, SensorDevice
from database.seed import seed
from .auth import create_access_token, decode_access_token, hash_password, verify_password, TokenError
from .pipeline import IngestionPipeline
from .repository import InMemoryRepository
from .sqlite_repo import SqliteDB, SqliteRepository, SqliteAlertStore
from .replay import ingest_batch
from .ws_manager import ConnectionManager
from .simulator_manager import SimulatorManager
from services.alert_engine.engine import AlertStore, AlertEngineError, InvalidTransition
from services.nlp_engine.engine import analyze_note
from services.alert_engine.ladder import EscalationLadder, ack_metrics, LEVELS
from services.care_engine.checkins import sweep_missed_visits, visit_status
from services.notify.channels import Dispatcher
from apps.simulator.equipment import OxygenConcentrator, IvPump, equipment_alert, FAULTS
from apps.simulator.scenarios import SCENARIOS

app = FastAPI(title="WardZero AI API",
             description="Clinical decision-support prototype — not a medical diagnosis or "
                         "emergency-response substitute. All patients are synthetic demo data.")
# CORS: was allow_origins=["*"]. Now an explicit allow-list from WZ_CORS_ORIGINS (comma-separated),
# defaulting to the local Vite dev server. In dev the Vite proxy makes the browser same-origin anyway
# (see apps/web/vite.config.ts), so this only matters for a separately-hosted production frontend.
_cors_origins = [o.strip() for o in os.environ.get(
    "WZ_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["GET", "POST", "OPTIONS"],
                  allow_headers=["Authorization", "Content-Type"])

# Persistence: readings, risk assessments, timeline, notes, device state, check-ins and ALERTS live in a
# durable SQLite file (WAL + synchronous=FULL; see apps/api/sqlite_repo.py), so history and alert audit
# trails survive restarts and power loss. Set WZ_SQLITE_PATH=":memory:" for an ephemeral run, or
# WZ_STORAGE=memory to use the old in-process repository. (Users/patients/devices registry still use
# SQLAlchemy via database/session.py.)
if os.environ.get("WZ_STORAGE", "sqlite") == "memory":
    _db = None
    _repo = InMemoryRepository()
    _alerts = AlertStore()
else:
    _db = SqliteDB(os.environ.get("WZ_SQLITE_PATH", "data/wardzero.db"))
    _repo = SqliteRepository(_db)
    _alerts = SqliteAlertStore(_db)
_pipeline = IngestionPipeline(_repo, alert_store=_alerts)
_ws = ConnectionManager()
_sim = SimulatorManager(_pipeline, _repo, _ws)  # STEP 12 (this session) — see simulator_manager.py


# ---- Phase 3: notifications (Telegram / ntfy / in-app), escalation ladder, equipment, missed visits
_STARTED = datetime.now(timezone.utc)
_dispatcher = Dispatcher.from_env(_repo if hasattr(_repo, "log_notification") else None, in_app_sink=_ws.broadcast_sync)
_equipment: dict[str, dict] = {}


def _notify(alert, level_name: str, level: int) -> None:
    """Called by the ladder every time an alert reaches a new level (L1 = first announcement)."""
    sev = alert.severity.value
    title = f"WardZero {sev.upper()} - patient {alert.patient_id} (to: {level_name})"
    body = (alert.risk_assessment or {}).get("explanation", alert.alert_type)[:500]
    _dispatcher.send(title, body, sev, alert.id)
    _ws.broadcast_sync({"type": "ladder", "alert_id": alert.id, "patient_id": alert.patient_id, "level": level, "recipient": level_name})


_ladder = EscalationLadder(_alerts, notify=_notify)


def _equip(patient_id: str) -> dict:
    return _equipment.setdefault(patient_id, {"oxygen": OxygenConcentrator(f"{patient_id}-o2"), "pump": IvPump(f"{patient_id}-pump")})


def _housekeeping_once() -> None:
    for pid, eq in list(_equipment.items()):
        for ev in eq["oxygen"].tick() + eq["pump"].tick():
            equipment_alert(_alerts, pid, ev)
    if hasattr(_repo, "last_checkin"):
        pts = [{"id": r["patient_id"], "risk_level": ((_repo.latest_risk_assessment(r["patient_id"]) or {}).get("risk_level") or "UNKNOWN"),
                "monitoring_since": _STARTED.isoformat()} for r in (_sim.status() or [])]
        sweep_missed_visits(_repo, _alerts, pts)
    _ladder.tick()


async def _housekeeping_loop():
    while True:
        try:
            await asyncio.to_thread(_housekeeping_once)
        except Exception:      # a housekeeping failure must never take the API down
            pass
        await asyncio.sleep(float(os.environ.get("WZ_HOUSEKEEPING_SECONDS", "15")))


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_housekeeping_loop())
    loop = asyncio.get_running_loop()
    _ws.bind_loop(loop)
    _sim.bind_loop(loop)
    init_db()
    seed()


# ---------------------------------------------------------------- auth
# Plain pattern instead of pydantic.EmailStr: EmailStr needs the extra `email-validator` package AND rejects
# special-use domains such as the seeded demo accounts (admin@wardzero.local).
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class SignUpBody(BaseModel):
    full_name: str
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str
    role: str = "caregiver"  # self-registration only ever yields "caregiver" — see signup() below


class SignInBody(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str


@app.post("/auth/signup")
def signup(body: SignUpBody):
    # SECURITY FIX (this pass): this route used to accept role="administrator" from the request body,
    # so anyone on the network could self-register as an administrator and receive an admin JWT —
    # privilege escalation by design. Public sign-up is now least-privilege only; administrator
    # accounts come from database/seed.py (or a future admin-only user-management route), never from
    # an unauthenticated request. The `role` field is kept in the body so existing clients don't break,
    # but any privileged value is refused rather than silently downgraded, so the caller finds out.
    if body.role != RoleEnum.caregiver.value:
        raise HTTPException(403, "self-registration is limited to the caregiver role")
    with get_session() as db:
        if db.query(User).filter_by(email=body.email).first():
            raise HTTPException(409, "email already registered")
        try:
            pw_hash = hash_password(body.password)
        except ValueError as e:
            raise HTTPException(400, str(e))
        user = User(full_name=body.full_name, email=body.email,
                   password_hash=pw_hash, role=RoleEnum.caregiver)
        db.add(user)
        db.flush()
        token = create_access_token(user.id, user.email, user.role.value)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/signin")
def signin(body: SignInBody):
    with get_session() as db:
        user = db.query(User).filter_by(email=body.email).first()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "invalid email or password")
        token = create_access_token(user.id, user.email, user.role.value)
    return {"access_token": token, "token_type": "bearer"}


def get_current_user(authorization: str | None = Header(default=None)):
    # BUG FIX (this session): `authorization` was previously a plain function parameter with no
    # Header() default, so FastAPI would have bound it as a query parameter (?authorization=...)
    # instead of reading the actual Authorization request header — every authenticated route would
    # have 401'd against a real client. Caught while wiring the frontend's fetch client against this
    # file; nothing about the JWT logic itself (apps/api/auth.py, already unit-tested) changed.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        return decode_access_token(authorization.removeprefix("Bearer "))
    except TokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {"id": user["sub"], "email": user["email"], "role": user["role"]}


# ---------------------------------------------------------------- ingestion (IoT -> pipeline)
@app.post("/readings")
def post_reading(raw_event: dict, patient_context: dict, note_signals: dict | None = None,
                 user=Depends(get_current_user)):
    """VALIDATE -> DEDUPE -> STORE -> FEATURES -> RISK -> ALERT -> NOTIFICATION -> TIMELINE.
    On success, broadcasts the notification to every connected websocket client so the frontend
    updates without a manual refresh (STEP 11)."""
    result = _pipeline.ingest(raw_event, patient_context, note_signals)
    if result.notification:
        _ws.broadcast_sync(result.notification)
    return result.to_dict()


class BatchBody(BaseModel):
    items: list[dict]


@app.post("/readings/batch")
def post_readings_batch(body: BatchBody, user=Depends(get_current_user)):
    """Idempotent replay endpoint for the client/edge offline queue (see apps/api/replay.py)."""
    try:
        return ingest_batch(_pipeline, body.items, notifier=_ws.broadcast_sync)
    except ValueError as e:
        raise HTTPException(413, str(e))


# ---------------------------------------------------------------- alerts
@app.get("/alerts")
def list_alerts(patient_id: str | None = None, open_only: bool = True, user=Depends(get_current_user)):
    return [a.to_dict() for a in _alerts.list(patient_id=patient_id, open_only=open_only)]


class ActionBody(BaseModel):
    reason: str | None = None
    note: str | None = None


@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int, user=Depends(get_current_user)):
    try:
        return _alerts.acknowledge(alert_id, user["email"]).to_dict()
    except (AlertEngineError, InvalidTransition) as e:
        raise HTTPException(400, str(e))


@app.post("/alerts/{alert_id}/dismiss")
def dismiss(alert_id: int, body: ActionBody, user=Depends(get_current_user)):
    try:
        return _alerts.dismiss(alert_id, user["email"], reason=body.reason or "").to_dict()
    except (AlertEngineError, InvalidTransition) as e:
        raise HTTPException(400, str(e))


@app.post("/alerts/{alert_id}/escalate")
def escalate(alert_id: int, user=Depends(get_current_user)):
    try:
        return _alerts.escalate(alert_id, actor=user["email"]).to_dict()
    except (AlertEngineError, InvalidTransition) as e:
        raise HTTPException(400, str(e))


@app.post("/alerts/{alert_id}/respond")
def respond(alert_id: int, body: ActionBody, user=Depends(get_current_user)):
    try:
        return _alerts.mark_responded(alert_id, user["email"], note=body.note).to_dict()
    except (AlertEngineError, InvalidTransition) as e:
        raise HTTPException(400, str(e))


@app.post("/alerts/{alert_id}/resolve")
def resolve(alert_id: int, body: ActionBody, user=Depends(get_current_user)):
    try:
        return _alerts.resolve(alert_id, user["email"], note=body.note).to_dict()
    except (AlertEngineError, InvalidTransition) as e:
        raise HTTPException(400, str(e))


@app.post("/alerts/{alert_id}/note")
def add_note(alert_id: int, body: ActionBody, user=Depends(get_current_user)):
    return _alerts.add_note(alert_id, user["email"], body.note or "").to_dict()


@app.get("/alerts/metrics")
def alert_metrics(user=Depends(get_current_user)):
    """Time-to-acknowledge statistics and ladder distribution, computed from real audit events."""
    return {**ack_metrics(_alerts), "ladder_levels": LEVELS}


@app.get("/notifications/channels")
def notification_channels(user=Depends(get_current_user)):
    return {c.name: bool(c.configured) for c in _dispatcher.channels}


@app.get("/notifications/log")
def notification_log(user=Depends(get_current_user)):
    return _repo.notifications() if hasattr(_repo, "notifications") else []


class CheckInBody(BaseModel):
    note: str | None = None


@app.post("/patients/{patient_id}/checkins")
def post_checkin(patient_id: str, body: CheckInBody, user=Depends(get_current_user)):
    rec = _repo.store_checkin(patient_id, user["email"], note=body.note)
    _repo.add_timeline_event(patient_id, "caregiver_checkin", {"caregiver": user["email"]})
    return rec


@app.get("/patients/{patient_id}/visit-status")
def get_visit_status(patient_id: str, user=Depends(get_current_user)):
    last = _repo.last_checkin(patient_id)
    risk = (_repo.latest_risk_assessment(patient_id) or {}).get("risk_level", "UNKNOWN")
    return {"risk_level": risk, "checkins": _repo.checkins_for(patient_id)[-10:],
            **visit_status(last["ts"] if last else None, risk, datetime.now(timezone.utc), since=_STARTED)}


class FaultBody(BaseModel):
    device: str            # "oxygen" | "pump"
    fault: str
    active: bool = True


@app.get("/patients/{patient_id}/equipment")
def get_equipment(patient_id: str, user=Depends(get_current_user)):
    eq = _equip(patient_id)
    o2, pump = eq["oxygen"], eq["pump"]
    return {"oxygen": {"device_id": o2.device_id, "flow_lpm": round(o2.flow_lpm, 2), "purity_pct": round(o2.purity_pct, 1),
                       "temp_c": round(o2.temp_c, 1), "mains": o2.mains, "active_faults": sorted(o2._faults)},
            "pump": {"device_id": pump.device_id, "rate_ml_h": pump.rate_ml_h, "volume_ml": round(pump.volume_ml, 1),
                     "battery_pct": round(pump.battery_pct, 1), "active_faults": sorted(pump._faults)},
            "available_faults": {k: v[1] for k, v in FAULTS.items()}, "simulated": True}


@app.post("/patients/{patient_id}/equipment/fault")
def set_fault(patient_id: str, body: FaultBody, user=Depends(get_current_user)):
    if body.fault not in FAULTS or body.device not in ("oxygen", "pump"):
        raise HTTPException(400, "unknown device or fault")
    dev = _equip(patient_id)[body.device]
    (dev.inject if body.active else dev.clear)(body.fault)
    _housekeeping_once()       # raise the alert immediately rather than waiting for the next sweep
    return get_equipment(patient_id, user)


# ---------------------------------------------------------------- timeline
@app.get("/patients/{patient_id}/timeline")
def timeline(patient_id: str, user=Depends(get_current_user)):
    return _repo.timeline_for(patient_id)


# ---------------------------------------------------------------- STEP 12 (this session)
# Additive frontend-integration API. Nothing here touches ml/, services/risk_engine,
# services/alert_engine, services/nlp_engine or apps/simulator's actual logic — these routes only
# read database/models.py rows (already written in STEP 9) and the in-memory repo/alert-store that
# the rest of this file already maintains, so the AI/ML/IoT-simulation code paths are unchanged.
# ** VERIFICATION STATUS: WRITTEN, NOT EXECUTED — same reason as the rest of this file. **

def _profile_dict(profile: PatientProfile | None) -> dict:
    if profile is None:
        return {}
    return {"hypertension": profile.hypertension, "diabetes": profile.diabetes,
           "cardiac": profile.cardiac, "copd": profile.copd, "post_surgery": profile.post_surgery,
           "preferred_language": profile.preferred_language, "notes": profile.notes}


def _condition_labels(profile: PatientProfile | None) -> list[str]:
    if profile is None:
        return []
    labels = {"hypertension": "Hypertension", "diabetes": "Diabetes", "cardiac": "Cardiac",
             "copd": "COPD", "post_surgery": "Post-Surgery"}
    return [v for k, v in labels.items() if getattr(profile, k, False)]


def _patient_summary(p: Patient, profile: PatientProfile | None) -> dict:
    latest_reading = _repo.latest_reading(p.id)
    latest_assessment = _repo.latest_risk_assessment(p.id)
    open_alerts = _alerts.list(patient_id=p.id, open_only=True)
    sim_status = _sim.status(p.id)
    return {
        "id": p.id, "full_name": p.full_name, "age": p.age, "is_synthetic_demo": p.is_synthetic_demo,
        "conditions": _condition_labels(profile), "profile": _profile_dict(profile),
        "risk_level": (latest_assessment or {}).get("risk_level", "unknown"),
        "risk_probability": (latest_assessment or {}).get("probability"),
        "latest_reading": latest_reading, "active_alert_count": len(open_alerts),
        "connectivity": (sim_status or {}).get("status", "no_data"),
        "simulation_running": bool(sim_status and sim_status.get("status") == "running"),
    }


@app.get("/patients")
def list_patients(user=Depends(get_current_user)):
    with get_session() as db:
        patients = db.query(Patient).order_by(Patient.full_name).all()
        return [_patient_summary(p, p.profile) for p in patients]


@app.get("/patients/{patient_id}")
def get_patient(patient_id: str, user=Depends(get_current_user)):
    with get_session() as db:
        p = db.get(Patient, patient_id)
        if not p:
            raise HTTPException(404, "patient not found")
        return _patient_summary(p, p.profile)


@app.get("/patients/{patient_id}/readings")
def patient_readings(patient_id: str, limit: int = 200, user=Depends(get_current_user)):
    """Real stored reading history for this patient (STEP 13 — this pass).

    Closes a documented gap (STATUS.md "Real API gaps discovered while wiring the frontend", #1):
    previously the only source of more-than-one-point vitals history was the live `sim_reading`
    WebSocket broadcast, so charts were empty on every page load until a simulation was actively
    running in that browser tab. `_repo.readings_for()` already stores every accepted reading
    (tests/test_pipeline.py exercises it) — this endpoint only exposes it over HTTP; no new storage
    or inference logic was added. Still honestly limited: `_repo` is an in-process, in-memory store
    (see repository.py docstring), so history resets on API restart and is shared across whichever
    browser tabs are open — it is not yet a persisted database, which remains a documented gap
    (see docs/limitations.md).
    """
    with get_session() as db:
        if not db.get(Patient, patient_id):
            raise HTTPException(404, "patient not found")
    limit = max(1, min(limit, 2000))
    return {"patient_id": patient_id, "readings": _repo.readings_for(patient_id, limit=limit)}


@app.get("/devices")
def list_devices(patient_id: str | None = None, user=Depends(get_current_user)):
    with get_session() as db:
        q = db.query(SensorDevice)
        if patient_id:
            q = q.filter_by(patient_id=patient_id)
        out = []
        for d in q.all():
            live = _repo.device_state(d.id) or {}
            connectivity = live.get("connectivity", "offline")
            # connection_status: PROMPT 4 section 4/5 explicitly requires the UI be able to
            # distinguish REAL HARDWARE from SIMULATED DEVICE from OFFLINE from UNKNOWN, rather than
            # a single ambiguous "online". is_simulated is always True in this build (no physical
            # hardware exists to connect) — "real_hardware" is included for forward-compatibility with
            # apps/api/device_adapter.py's HttpDeviceAdapter/MqttDeviceAdapter but can never actually be
            # returned by *this* deployment's data, and nothing here claims otherwise.
            if not live:
                connection_status = "unknown"
            elif connectivity != "online":
                connection_status = "offline"
            elif d.is_simulated:
                connection_status = "simulated"
            else:
                connection_status = "real_hardware"  # unreachable while is_simulated is always True
            out.append({"id": d.id, "patient_id": d.patient_id, "device_type": d.device_type,
                       "location": d.location, "is_simulated": d.is_simulated,
                       "connectivity": connectivity, "connection_status": connection_status,
                       "battery_pct": live.get("battery", d.battery_pct),
                       "last_seen": live.get("last_seen"),
                       "manufacturer": d.manufacturer, "device_model": d.device_model,
                       "firmware_version": d.firmware_version, "protocol": d.protocol,
                       "registered_at": d.registered_at.isoformat() if d.registered_at else None,
                       "recent_events": _repo.device_events_for(d.id, limit=5)})
        return out


@app.get("/caregivers")
def list_caregivers(user=Depends(get_current_user)):
    all_alerts = _alerts.list(open_only=False)
    with get_session() as db:
        users = db.query(User).filter_by(role=RoleEnum.caregiver).all()
        out = []
        for u in users:
            actions = []
            for a in all_alerts:
                d = a.to_dict()
                for ev in d.get("audit", []):
                    if ev.get("actor") == u.email:
                        actions.append({"alert_id": d["id"], "patient_id": d["patient_id"],
                                       **ev})
            actions.sort(key=lambda a: a["ts"], reverse=True)
            out.append({"id": u.id, "full_name": u.full_name, "email": u.email,
                       "recent_actions": actions[:10]})
        return out


@app.get("/analytics/summary")
def analytics_summary(user=Depends(get_current_user)):
    with get_session() as db:
        patients = db.query(Patient).all()
        summaries = [_patient_summary(p, p.profile) for p in patients]
    dist = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for s in summaries:
        level = (s["risk_level"] or "unknown").lower()
        dist[level if level in dist else "unknown"] += 1
    all_alerts = _alerts.list(open_only=False)
    return {
        "total_patients": len(summaries),
        "risk_distribution": dist,
        "active_alerts": len(_alerts.list(open_only=True)),
        "total_alerts": len(all_alerts),
        "repo_counts": _repo.counts(),
        "simulations_running": len([s for s in _sim.status() if s["status"] == "running"]),
    }


@app.get("/system/health")
def system_health(user=Depends(get_current_user)):
    with get_session() as db:
        db_ok = True
        try:
            db.query(User).first()
        except Exception:
            db_ok = False
    return {
        "api": "ok",
        "database": "ok" if db_ok else "unavailable",
        "websocket_connections": len(_ws._connections),
        "ai_engine": "ok",  # services/risk_engine falls back to rules internally if the model is
                            # unavailable (STATUS.md item 5) rather than this endpoint faking "ok"
        "simulator": {"active_runs": len(_sim.runs)},
        "repo_counts": _repo.counts(),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/scenarios")
def list_scenarios(user=Depends(get_current_user)):
    return _sim.available_scenarios()


class NoteBody(BaseModel):
    patient_id: str
    text: str
    language: str | None = None


@app.post("/notes/analyze")
def analyze_note_route(body: NoteBody, user=Depends(get_current_user)):
    """Thin wrapper around services/nlp_engine/engine.analyze_note — the NLP logic itself is
    unchanged and already unit-tested (20/20, per STATUS.md). This route only adds HTTP plumbing
    and persists the result via the new repo.store_note so /notes/{patient_id} can show history."""
    try:
        result = analyze_note(body.text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    stored = _repo.store_note(body.patient_id, {"text": body.text, "language": body.language,
                                                "result": result, "author": user["email"],
                                                "created_at": datetime.now(timezone.utc).isoformat()})
    _repo.add_timeline_event(body.patient_id, "caregiver_note", {"note_id": stored["id"],
                                                                 "present": result["present"]})
    return stored


@app.get("/patients/{patient_id}/notes")
def notes_for_patient(patient_id: str, user=Depends(get_current_user)):
    return _repo.notes_for(patient_id)


class SimControlBody(BaseModel):
    scenario: str = "normal"
    speed: float = 1.0
    custom: dict | None = None


@app.post("/simulator/{patient_id}/start")
def sim_start(patient_id: str, body: SimControlBody, user=Depends(get_current_user)):
    if body.scenario not in SCENARIOS and body.scenario != "custom":
        raise HTTPException(400, f"unknown scenario: {body.scenario}")
    with get_session() as db:
        p = db.get(Patient, patient_id)
        if not p:
            raise HTTPException(404, "patient not found")
        profile = _profile_dict(p.profile)
        profile["age"] = p.age
        device_id = f"{patient_id}-vitals"
    return _sim.start(patient_id, device_id, profile, body.scenario, body.speed, body.custom)


@app.post("/simulator/{patient_id}/pause")
def sim_pause(patient_id: str, user=Depends(get_current_user)):
    run = _sim.pause(patient_id)
    if run is None:
        raise HTTPException(404, "no simulation running for this patient")
    return run


@app.post("/simulator/{patient_id}/stop")
def sim_stop(patient_id: str, user=Depends(get_current_user)):
    run = _sim.stop(patient_id)
    if run is None:
        raise HTTPException(404, "no simulation running for this patient")
    return run


@app.post("/simulator/{patient_id}/reset")
def sim_reset(patient_id: str, body: SimControlBody, user=Depends(get_current_user)):
    with get_session() as db:
        p = db.get(Patient, patient_id)
        if not p:
            raise HTTPException(404, "patient not found")
        profile = _profile_dict(p.profile)
        profile["age"] = p.age
        device_id = f"{patient_id}-vitals"
    return _sim.reset(patient_id, device_id, profile, body.scenario, body.speed, body.custom)


@app.get("/simulator/status")
def sim_status_all(user=Depends(get_current_user)):
    return _sim.status()


@app.get("/simulator/{patient_id}/status")
def sim_status_one(patient_id: str, user=Depends(get_current_user)):
    run = _sim.status(patient_id)
    return run or {"patient_id": patient_id, "status": "stopped"}


@app.get("/reports/{patient_id}")
def patient_report(patient_id: str, user=Depends(get_current_user)):
    """Structured JSON report assembled entirely from real backend state (profile, timeline, latest
    risk assessment, alert history) — no invented figures. See docs/reports.md for the PDF export
    path (reportlab), added to requirements.txt this session, which renders this same dict."""
    with get_session() as db:
        p = db.get(Patient, patient_id)
        if not p:
            raise HTTPException(404, "patient not found")
        summary = _patient_summary(p, p.profile)
    return {
        "patient": summary,
        # Full explainable assessment (contributing_factors/forecast/explanation/trend), not just the
        # risk_level/probability scalars _patient_summary exposes — closes STATUS.md gap #2 for the
        # one read-only endpoint (a report) where showing the complete picture matters most and there
        # is no WebSocket connection to fall back on. Real stored state; None if none exists yet.
        "risk_assessment": _repo.latest_risk_assessment(patient_id),
        "timeline": _repo.timeline_for(patient_id),
        "alerts": [a.to_dict() for a in _alerts.list(patient_id=patient_id, open_only=False)],
        "notes": _repo.notes_for(patient_id),
        "device_events": _repo.device_events_for(f"{patient_id}-vitals", limit=20),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Clinical decision-support prototype — not a medical diagnosis or "
                     "emergency-response substitute. All patients are synthetic demo data.",
    }


@app.get("/reports/{patient_id}/pdf")
def patient_report_pdf(patient_id: str, user=Depends(get_current_user)):
    """Real PDF rendering of the exact dict patient_report() above returns (STEP 13 — this pass).

    Uses reportlab (now installed — see requirements.txt and docs/reports.md for the history of this
    gap). render_patient_report_pdf() is framework-independent and unit-tested on its own
    (tests/test_report_pdf.py renders a report and parses the bytes back out with pypdf to assert the
    real content is present) — this route is the same thin, unexecuted FastAPI wrapper as everything
    else in this file, adding only HTTP plumbing around already-tested logic.
    """
    from fastapi import Response
    from .reports_pdf import render_patient_report_pdf
    report = patient_report(patient_id, user=user)
    pdf_bytes = render_patient_report_pdf(report)
    filename = f"wardzero-report-{patient_id}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ---------------------------------------------------------------- realtime (STEP 11)
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # SECURITY FIX (this pass): the socket used to accept anyone and broadcast patient vitals/alerts to
    # them. Browsers cannot set an Authorization header on a WebSocket, so the JWT arrives as a
    # `?token=` query parameter and is validated with the same decode_access_token() the REST routes
    # use. Invalid/missing/expired token -> close with 1008 (policy violation) before accept().
    # Trade-off: a token in a URL can appear in server access logs — keep access-log query strings off
    # in production, and prefer short-lived tokens (WZ_JWT_EXPIRE_MINUTES).
    try:
        decode_access_token(websocket.query_params.get("token", ""))
    except TokenError:
        await websocket.close(code=1008)
        return
    await _ws.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # clients don't need to send anything; keeps conn open
    except WebSocketDisconnect:
        pass
    finally:
        # always drop the socket, whatever ended the loop (a clean disconnect, a RuntimeError from a
        # half-closed connection, cancellation at shutdown) so dead sockets never accumulate
        _ws.disconnect(websocket)


# ---------------------------------------------------------------- health
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat(),
           "disclaimer": "Clinical decision-support prototype — not a medical diagnosis or "
                         "emergency-response substitute."}
