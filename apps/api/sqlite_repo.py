"""Durable SQLite persistence for readings, risk assessments, timeline, notes, device state, check-ins,
alerts and notification log. Stdlib `sqlite3` only (no SQLAlchemy needed), so it runs and is tested
everywhere Python runs.

Same method signatures as apps.api.repository.InMemoryRepository, so IngestionPipeline works with either.

Power-loss / crash safety:
  * WAL journal + synchronous=FULL: a committed transaction survives process kill and power loss
    (tests/test_resilience.py SIGKILLs a writer process mid-stream and re-opens the file).
  * `readings.event_id` is the PRIMARY KEY and inserts use INSERT OR IGNORE, so replaying the same event
    (client retry after a dropped connection) is idempotent at the storage layer, not only in the pipeline.
  * `readings_for` orders by sensor timestamp, so late / out-of-order events land in clinical order.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

from services.alert_engine.engine import Alert, AlertStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, patient_id TEXT NOT NULL,
  ts_epoch REAL NOT NULL, data TEXT NOT NULL, received_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_readings_patient_ts ON readings(patient_id, ts_epoch, seq);
CREATE TABLE IF NOT EXISTS rejected (id INTEGER PRIMARY KEY AUTOINCREMENT, raw TEXT, errors TEXT, received_at TEXT);
CREATE TABLE IF NOT EXISTS timeline (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL,
  kind TEXT NOT NULL, detail TEXT NOT NULL, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_timeline_patient ON timeline(patient_id, id);
CREATE TABLE IF NOT EXISTS risk_assessments (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL,
  data TEXT NOT NULL, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_risk_patient ON risk_assessments(patient_id, id);
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS device_events (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS device_state (device_id TEXT PRIMARY KEY, connectivity TEXT, battery INTEGER, last_seen TEXT);
CREATE TABLE IF NOT EXISTS checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL,
  caregiver TEXT NOT NULL, ts TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, patient_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notification_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
  channel TEXT NOT NULL, ok INTEGER NOT NULL, alert_id INTEGER, detail TEXT);
"""


def _epoch(ts) -> float:
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteDB:
    """One shared connection guarded by a lock (the API serves from a thread pool + an event loop)."""

    def __init__(self, path: str = "data/wardzero.db"):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)  # autocommit; we BEGIN explicitly
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=FULL")
            self.conn.executescript(SCHEMA)

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self.lock:
            self.conn.close()


class SqliteRepository:
    def __init__(self, db: SqliteDB | str = "data/wardzero.db"):
        self.db = db if isinstance(db, SqliteDB) else SqliteDB(db)

    # -- readings ---------------------------------------------------------
    def is_duplicate(self, event_id: str) -> bool:
        return bool(self.db.query("SELECT 1 FROM readings WHERE event_id=?", (event_id,)))

    def store_reading(self, patient_id: str, reading: dict) -> bool:
        """Returns True if newly stored, False if this event_id was already present (idempotent)."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO readings(event_id, patient_id, ts_epoch, data, received_at) VALUES (?,?,?,?,?)",
            (reading["event_id"], patient_id, _epoch(reading.get("timestamp")), json.dumps(reading), _now()))
        return cur.rowcount == 1

    def store_rejected(self, raw: dict, errors: list[str]) -> None:
        self.db.execute("INSERT INTO rejected(raw, errors, received_at) VALUES (?,?,?)",
                        (json.dumps(raw, default=str), json.dumps(errors), _now()))

    def readings_for(self, patient_id: str, limit: int | None = None) -> list[dict]:
        if limit:
            rows = self.db.query("SELECT data FROM (SELECT data, ts_epoch, seq FROM readings WHERE patient_id=? "
                                 "ORDER BY ts_epoch DESC, seq DESC LIMIT ?) ORDER BY ts_epoch, seq", (patient_id, limit))
        else:
            rows = self.db.query("SELECT data FROM readings WHERE patient_id=? ORDER BY ts_epoch, seq", (patient_id,))
        return [json.loads(r["data"]) for r in rows]

    def latest_reading(self, patient_id: str) -> dict | None:
        rows = self.db.query("SELECT data FROM readings WHERE patient_id=? ORDER BY ts_epoch DESC, seq DESC LIMIT 1", (patient_id,))
        return json.loads(rows[0]["data"]) if rows else None

    # -- risk assessments ---------------------------------------------------
    def store_risk_assessment(self, patient_id: str, assessment: dict) -> None:
        self.db.execute("INSERT INTO risk_assessments(patient_id, data, ts) VALUES (?,?,?)",
                        (patient_id, json.dumps(assessment), _now()))

    def latest_risk_assessment(self, patient_id: str) -> dict | None:
        rows = self.db.query("SELECT data FROM risk_assessments WHERE patient_id=? ORDER BY id DESC LIMIT 1", (patient_id,))
        return json.loads(rows[0]["data"]) if rows else None

    # -- timeline -------------------------------------------------------
    def add_timeline_event(self, patient_id: str, kind: str, detail: dict) -> dict:
        ts = _now()
        cur = self.db.execute("INSERT INTO timeline(patient_id, kind, detail, ts) VALUES (?,?,?,?)",
                              (patient_id, kind, json.dumps(detail, default=str), ts))
        return {"id": cur.lastrowid, "patient_id": patient_id, "kind": kind, "detail": detail, "ts": ts}

    def timeline_for(self, patient_id: str) -> list[dict]:
        return [{"id": r["id"], "patient_id": r["patient_id"], "kind": r["kind"],
                 "detail": json.loads(r["detail"]), "ts": r["ts"]}
                for r in self.db.query("SELECT * FROM timeline WHERE patient_id=? ORDER BY id", (patient_id,))]

    # -- notes ---------------------------------------------------------
    def store_note(self, patient_id: str, note: dict) -> dict:
        cur = self.db.execute("INSERT INTO notes(patient_id, data) VALUES (?,?)", (patient_id, json.dumps(note, default=str)))
        return {**note, "id": cur.lastrowid}

    def notes_for(self, patient_id: str) -> list[dict]:
        return [{**json.loads(r["data"]), "id": r["id"]}
                for r in self.db.query("SELECT id, data FROM notes WHERE patient_id=? ORDER BY id", (patient_id,))]

    # -- devices -------------------------------------------------------
    def set_device_state(self, device_id: str, connectivity: str, battery: int | None) -> None:
        self.db.execute("INSERT INTO device_state(device_id, connectivity, battery, last_seen) VALUES (?,?,?,?) "
                        "ON CONFLICT(device_id) DO UPDATE SET connectivity=excluded.connectivity, "
                        "battery=excluded.battery, last_seen=excluded.last_seen",
                        (device_id, connectivity, battery, _now()))

    def device_state(self, device_id: str) -> dict | None:
        rows = self.db.query("SELECT * FROM device_state WHERE device_id=?", (device_id,))
        if not rows:
            return None
        r = rows[0]
        return {"connectivity": r["connectivity"], "battery": r["battery"], "last_seen": r["last_seen"]}

    def store_device_event(self, device_id: str, event: dict) -> dict:
        cur = self.db.execute("INSERT INTO device_events(device_id, data) VALUES (?,?)", (device_id, json.dumps(event, default=str)))
        return {**event, "id": cur.lastrowid}

    def device_events_for(self, device_id: str, limit: int = 20) -> list[dict]:
        rows = self.db.query("SELECT id, data FROM (SELECT id, data FROM device_events WHERE device_id=? ORDER BY id DESC LIMIT ?) ORDER BY id",
                             (device_id, limit or 1000000))
        return [{**json.loads(r["data"]), "id": r["id"]} for r in rows]

    # -- caregiver check-ins (Phase 3) ---------------------------------------
    def store_checkin(self, patient_id: str, caregiver: str, ts: str | None = None, note: str | None = None) -> dict:
        ts = ts or _now()
        cur = self.db.execute("INSERT INTO checkins(patient_id, caregiver, ts, note) VALUES (?,?,?,?)", (patient_id, caregiver, ts, note))
        return {"id": cur.lastrowid, "patient_id": patient_id, "caregiver": caregiver, "ts": ts, "note": note}

    def checkins_for(self, patient_id: str) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT * FROM checkins WHERE patient_id=? ORDER BY ts", (patient_id,))]

    def last_checkin(self, patient_id: str) -> dict | None:
        rows = self.db.query("SELECT * FROM checkins WHERE patient_id=? ORDER BY ts DESC LIMIT 1", (patient_id,))
        return dict(rows[0]) if rows else None

    # -- notification log ------------------------------------------------
    def log_notification(self, channel: str, ok: bool, alert_id: int | None, detail: str = "") -> None:
        self.db.execute("INSERT INTO notification_log(ts, channel, ok, alert_id, detail) VALUES (?,?,?,?,?)",
                        (_now(), channel, 1 if ok else 0, alert_id, detail))

    def notifications(self, limit: int = 100) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT * FROM notification_log ORDER BY id DESC LIMIT ?", (limit,))]

    # -- stats -------------------------------------------------------------
    def counts(self) -> dict:
        r = self.db.query("SELECT COUNT(*) n, COUNT(DISTINCT patient_id) p FROM readings")[0]
        rej = self.db.query("SELECT COUNT(*) n FROM rejected")[0]["n"]
        return {"patients_with_readings": r["p"], "total_readings": r["n"], "rejected": rej}


class SqliteAlertStore(AlertStore):
    """AlertStore that writes every state change through to SQLite and reloads open + closed alerts on start,
    so alerts, their audit trail and time-to-ack data survive an API restart."""

    def __init__(self, db: SqliteDB, clock=None):
        super().__init__(clock=clock)
        self.db = db
        for row in db.query("SELECT data FROM alerts ORDER BY id"):
            a = Alert.from_dict(json.loads(row["data"]))
            self._alerts[a.id] = a
        self._max_id = max(self._alerts, default=0)

    def _next_id(self) -> int:
        with self.db.lock:
            row = self.db.query("SELECT COALESCE(MAX(id),0) m FROM alerts")[0]
            self._max_id = max(self._max_id, row["m"]) + 1
            return self._max_id

    def _on_change(self, alert: Alert) -> None:
        self.db.execute("INSERT INTO alerts(id, patient_id, status, data) VALUES (?,?,?,?) "
                        "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                        (alert.id, alert.patient_id, alert.status.value, json.dumps(alert.to_dict())))
