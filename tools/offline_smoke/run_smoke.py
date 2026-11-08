"""Offline smoke test of apps/api/main.py WITHOUT fastapi/pydantic/sqlalchemy installed.

Run:  python3 tools/offline_smoke/run_smoke.py

WHAT THIS IS: tiny stand-ins for fastapi + pydantic (./fastapi, ./pydantic) and a fake SQLAlchemy layer let
main.py be imported and its route functions be called with real JWTs, the real pipeline, real SQLite
repository, real alert store and real simulator manager. It catches wiring bugs (wrong names, bad payload
shapes, thread/loop mistakes, broken lifecycle) that unit tests of the underlying modules cannot.

WHAT THIS IS NOT: it is not FastAPI. It does not test routing precedence, request validation (422s),
OpenAPI, CORS, real Starlette WebSockets, or the SQLAlchemy-backed routes (/patients, /devices,
/caregivers, /reports ... run against an EMPTY fake DB). Run the real thing (uvicorn + the curl smoke test)
when you have network access. Never import these stubs from application code.
"""
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import call, app, main            # noqa: E402  (importing harness installs the stubs)
from fastapi import WebSocketDisconnect        # noqa: E402
from apps.api.auth import create_access_token  # noqa: E402

TOK = create_access_token("u1", "nurse@wardzero.local", "caregiver")
CTX = {"age": 67, "hypertension": 1, "diabetes": 1, "cardiac": 0, "copd": 0, "post_surgery": 0}
T0 = time.time() - 3600
_fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        _fails.append(name)


def ev(eid, t, pid="demo-ravi-kumar", **o):
    b = {"event_id": eid, "patient_id": pid, "device_id": "dev-1", "timestamp": t, "heart_rate": 75, "spo2": 97,
         "temperature": 36.7, "resp_rate": 16, "systolic_bp": 124, "diastolic_bp": 78, "activity": 35,
         "device_state": "ok", "connectivity": "online"}
    b.update(o)
    return b


def auth_and_alert_flow():
    check("no token -> 401", call("GET", "/auth/me")[0] == 401)
    check("bad token -> 401", call("GET", "/auth/me", token="junk")[0] == 401)
    c, r = call("GET", "/auth/me", token=TOK)
    check("valid token -> identity", c == 200 and r["email"] == "nurse@wardzero.local")
    c, _ = call("POST", "/auth/signup", {"full_name": "x", "email": "a@b.co", "password": "pw12345678", "role": "administrator"})
    check("self-service admin sign-up refused (403)", c == 403)
    check("unknown user sign-in -> 401", call("POST", "/auth/signin", {"email": "a@b.co", "password": "pw"})[0] == 401)

    for i in range(12):
        c, r = call("POST", "/readings", {"raw_event": ev(f"e{i}", T0 + i * 300), "patient_context": CTX}, token=TOK)
    check("12 normal readings accepted, risk LOW", c == 200 and r["status"] == "accepted" and r["risk_assessment"]["risk_level"] == "LOW")
    check("no alert for stable patient", call("GET", "/alerts", token=TOK)[1] == [])
    for i in range(12, 20):
        call("POST", "/readings", {"raw_event": ev(f"e{i}", T0 + i * 300, heart_rate=135, spo2=86, resp_rate=29,
                                                   temperature=39.2, systolic_bp=88), "patient_context": CTX}, token=TOK)
    c, al = call("GET", "/alerts", token=TOK)
    check("deterioration raises a critical alert", c == 200 and len(al) == 1 and al[0]["severity"] == "critical")
    aid = al[0]["id"]
    states = []
    for act, body in [("acknowledge", None), ("escalate", None), ("respond", {"note": "on it"})]:
        c, r = call("POST", f"/alerts/{aid}/{act}", body, token=TOK)
        states.append(r["status"] if c == 200 else c)
    check("ack -> escalate -> respond lifecycle", states == ["ACKNOWLEDGED", "ESCALATED", "RESPONDED"], states)
    c, r = call("POST", f"/alerts/{aid}/dismiss", {"reason": "false alarm"}, token=TOK)
    check("dismissing a RESPONDED alert is refused (400)", c == 400, (c, r))
    c, r = call("POST", f"/alerts/{aid}/resolve", {"note": "O2 started"}, token=TOK)
    check("RESPONDED alert can be resolved", c == 200 and r["status"] == "RESOLVED", (c, r))
    c, m = call("GET", "/alerts/metrics", token=TOK)
    check("ack metrics computed from audit events", c == 200 and m["overall"]["n"] == 1)
    check("timeline has events", len(call("GET", "/patients/demo-ravi-kumar/timeline", token=TOK)[1]) > 10)
    c, _ = call("POST", "/patients/demo-ravi-kumar/checkins", {"note": "seen"}, token=TOK)
    c2, vs = call("GET", "/patients/demo-ravi-kumar/visit-status", token=TOK)
    check("check-in + visit-status", c == 200 and c2 == 200 and len(vs["checkins"]) == 1)
    c, eq = call("POST", "/patients/demo-ravi-kumar/equipment/fault",
                 {"device": "oxygen", "fault": next(iter(main.FAULTS)), "active": True}, token=TOK)
    check("equipment fault injected", c == 200 and eq["oxygen"]["active_faults"])
    check("unknown fault -> 400", call("POST", "/patients/demo-ravi-kumar/equipment/fault", {"device": "x", "fault": "nope"}, token=TOK)[0] == 400)
    c, n = call("POST", "/notes/analyze", {"patient_id": "demo-ravi-kumar", "text": "very breathless and dizzy"}, token=TOK)
    check("note analysis flags breathing difficulty", c == 200 and n["result"]["signals"]["breathing_difficulty"])


def batch_flow():
    items = [{"event": ev(f"b{i}", T0 + i * 60, pid="p-batch"), "context": CTX} for i in (3, 1, 2)]
    check("batch accepted", call("POST", "/readings/batch", {"items": items}, token=TOK)[1]["counts"]["accepted"] == 3)
    check("batch replay is idempotent", call("POST", "/readings/batch", {"items": items}, token=TOK)[1]["counts"]["duplicate"] == 3)
    check("oversized batch -> 413", call("POST", "/readings/batch", {"items": [{"event": {}}] * 501}, token=TOK)[0] == 413)


class FakeWS:
    def __init__(s, token):
        s.query_params = {} if token is None else {"token": token}
        s.sent, s.closed, s.accepted, s.q = [], None, False, asyncio.Queue()
    async def accept(s): s.accepted = True
    async def close(s, code=1000): s.closed = code
    async def send_text(s, t): s.sent.append(json.loads(t))
    async def receive_text(s):
        v = await s.q.get()
        if v == "DISC": raise WebSocketDisconnect()
        if v == "BOOM": raise RuntimeError("half closed")
        return v


async def websocket_and_sim_flow():
    ws_fn = next(f for m, p, _, f in app.routes if m == "WS")
    for f in app.startup:
        await f()
    bad, none = FakeWS("junk"), FakeWS(None)
    await ws_fn(bad); await ws_fn(none)
    check("ws: bad/missing token closed 1008 before accept", bad.closed == 1008 and none.closed == 1008 and not bad.accepted)
    good = FakeWS(TOK); t = asyncio.create_task(ws_fn(good)); await asyncio.sleep(0.1)
    check("ws: valid token accepted", good.accepted and len(main._ws._connections) == 1)
    await asyncio.to_thread(call, "POST", "/readings", {"raw_event": ev("w1", time.time(), pid="p-ws"), "patient_context": CTX}, None, TOK)
    await asyncio.sleep(0.3)
    check("ws: broadcast from a worker thread is delivered", [m.get("type") for m in good.sent] == ["vitals_update"], good.sent)
    good.q.put_nowait("BOOM")
    try: await t
    except RuntimeError: pass
    check("ws: socket removed even on a non-disconnect error", len(main._ws._connections) == 0)
    g2 = FakeWS(TOK); t2 = asyncio.create_task(ws_fn(g2)); await asyncio.sleep(0.1); g2.q.put_nowait("DISC"); await t2
    check("ws: socket removed on clean disconnect", len(main._ws._connections) == 0)

    class FP: age = 67; profile = None; full_name = "Demo"; id = "sim-p1"
    sys.modules["database.session"].get_session  # fake DB returns a patient for this part only
    import harness
    harness._DB.get = lambda self, *a: FP()
    main._profile_dict = lambda p: {"hypertension": True}
    c, r = call("POST", "/simulator/sim-p1/start", {"scenario": "breathing_deterioration", "speed": 60}, token=TOK)
    check("simulator start", c == 200 and r["status"] == "running")
    await asyncio.sleep(3)
    c, st = call("GET", "/simulator/status", token=TOK)
    check("simulator produced ticks via the server loop", c == 200 and st and st[0]["tick_count"] >= 5, st[0]["tick_count"] if st else st)
    check("simulator pause/stop", call("POST", "/simulator/sim-p1/pause", token=TOK)[0] == 200 and call("POST", "/simulator/sim-p1/stop", token=TOK)[0] == 200)


if __name__ == "__main__":
    auth_and_alert_flow()
    batch_flow()
    asyncio.run(websocket_and_sim_flow())
    print(f"\n{'ALL PASSED' if not _fails else 'FAILED: ' + ', '.join(_fails)}")
    sys.exit(1 if _fails else 0)
