"""SQLAlchemy 2.0 ORM models — STEP 9.

** VERIFICATION STATUS: WRITTEN BUT NOT EXECUTED. **
sqlalchemy is not installed in this sandbox and there is no network access to install it
(`pip install fastapi --break-system-packages` was attempted in this session and failed with
"No matching distribution found" — the sandbox has no outbound network at all). This file has been
reviewed for internal consistency (field names match services/alert_engine/engine.py's Alert
dataclass, services/sync_engine/queue.py's sync_queue table, and apps/api/repository.py's
InMemoryRepository, so swapping backends is mechanical) but it has NOT been imported, migrated,
or run against a real database. Treat it as a reviewed draft, not a tested artifact, until it is
run in an environment with sqlalchemy installed.

Entities (13, per spec STEP 9):
users, patients, patient_profiles, sensor_devices, sensor_readings, caregiver_notes,
risk_assessments, alerts, caregiver_actions, timeline_events, device_events, sync_queue, audit_logs
"""
from __future__ import annotations
from datetime import datetime, timezone
import enum

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text, Enum as SAEnum,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _now():
    return datetime.now(timezone.utc)


class RoleEnum(str, enum.Enum):
    caregiver = "caregiver"
    administrator = "administrator"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash, never plaintext
    role = Column(SAEnum(RoleEnum), nullable=False, default=RoleEnum.caregiver)
    created_at = Column(DateTime(timezone=True), default=_now)
    is_active = Column(Boolean, default=True)


class Patient(Base):
    __tablename__ = "patients"
    id = Column(String(64), primary_key=True)  # e.g. "demo-ravi-kumar"
    full_name = Column(String(200), nullable=False)
    age = Column(Integer, nullable=False)
    is_synthetic_demo = Column(Boolean, default=True, nullable=False)  # per spec: must be flagged
    created_at = Column(DateTime(timezone=True), default=_now)

    profile = relationship("PatientProfile", back_populates="patient", uselist=False)


class PatientProfile(Base):
    __tablename__ = "patient_profiles"
    id = Column(Integer, primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.id"), unique=True, nullable=False)
    hypertension = Column(Boolean, default=False)
    diabetes = Column(Boolean, default=False)
    cardiac = Column(Boolean, default=False)
    copd = Column(Boolean, default=False)
    post_surgery = Column(Boolean, default=False)
    preferred_language = Column(String(16), default="en")  # en | ta | te | hi | hi-romanized
    notes = Column(Text, nullable=True)

    patient = relationship("Patient", back_populates="profile")


class SensorDevice(Base):
    __tablename__ = "sensor_devices"
    id = Column(String(64), primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False)
    device_type = Column(String(64), nullable=False)  # heart_rate | spo2 | temperature | ... | camera
    location = Column(String(100), nullable=True)
    is_simulated = Column(Boolean, default=True, nullable=False)  # always True — no physical hardware
    status = Column(String(32), default="online")
    battery_pct = Column(Integer, nullable=True)
    # Registry fields added for PROMPT 4 section 5 ("Device Registry") — additive/nullable so this
    # doesn't disturb the existing, already-reviewed shape above. Populated with clearly-synthetic
    # values in database/seed.py (see comment there on why real-sounding vendor names are avoided).
    # is_simulated is always True in this build, so `protocol` is always "simulated" here too — the
    # column exists so a real HTTP/MQTT adapter (see apps/api/device_adapter.py) has somewhere to
    # honestly record itself if one is ever connected; nothing here claims that has happened.
    manufacturer = Column(String(100), nullable=True)
    device_model = Column(String(100), nullable=True)  # "model" avoided — ambiguous with ML model elsewhere
    firmware_version = Column(String(32), nullable=True)
    protocol = Column(String(16), nullable=True)  # "simulated" | "http" | "mqtt" (http/mqtt: not yet connected in this build)
    registered_at = Column(DateTime(timezone=True), default=_now)
    device_metadata = Column(JSON, nullable=True)  # NOT named `metadata` — that name is reserved by
                                                    # SQLAlchemy's declarative Base (Base.metadata);
                                                    # using it as a column name raises at class-definition
                                                    # time. Caught by review, not by running it (can't, here).
    # signal_strength is intentionally NOT a column here. The simulator has no signal-strength concept
    # to report, and adding an unpopulated numeric field invites a future author to fill it with a
    # plausible-looking fake number "just to complete the row" — exactly what PROMPT 3/4's "never
    # fabricate sensor readings" rule forbids. Add it when a real or simulated data source for it exists.


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id = Column(Integer, primary_key=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)  # dedup key
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    device_id = Column(String(64), ForeignKey("sensor_devices.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    heart_rate = Column(Float, nullable=True)
    spo2 = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    resp_rate = Column(Float, nullable=True)
    systolic_bp = Column(Float, nullable=True)
    diastolic_bp = Column(Float, nullable=True)
    activity = Column(Float, nullable=True)
    device_state = Column(String(32), nullable=True)
    connectivity = Column(String(16), nullable=True)
    scenario = Column(String(64), nullable=True)  # synthetic-data label; never shown as a real diagnosis
    received_at = Column(DateTime(timezone=True), default=_now)
    # NOTE: `_true_severity` from the simulator is intentionally NOT a column here — apps/api/validation.py
    # whitelists incoming fields and strips it before this row would ever be constructed.

    __table_args__ = (Index("ix_readings_patient_ts", "patient_id", "timestamp"),)


class CaregiverNote(Base):
    __tablename__ = "caregiver_notes"
    id = Column(Integer, primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    language = Column(String(16), nullable=False)  # en | ta | te | hi | hi-romanized
    raw_text = Column(Text, nullable=False)
    extracted_signals = Column(JSON, nullable=True)  # output of services.nlp_engine.engine
    created_at = Column(DateTime(timezone=True), default=_now)


class RiskAssessmentRow(Base):
    __tablename__ = "risk_assessments"
    id = Column(Integer, primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    risk_level = Column(String(16), nullable=False)
    probability = Column(Float, nullable=False)
    method = Column(String(16), nullable=False)  # "model" | "rules"
    contributing_factors = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)
    trend = Column(JSON, nullable=True)
    recommended_escalation = Column(String(32), nullable=False)
    forecast = Column(JSON, nullable=True)
    hard_threshold_breaches = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)


class AlertRow(Base):
    """Persisted mirror of services.alert_engine.engine.Alert. Field names match 1:1 with
    Alert.to_dict() so the in-memory AlertStore and a SQL-backed store share a serialization shape."""
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    alert_type = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, index=True)
    risk_assessment = Column(JSON, nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    dismiss_reason = Column(Text, nullable=True)


class CaregiverAction(Base):
    __tablename__ = "caregiver_actions"
    id = Column(Integer, primary_key=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(32), nullable=False)  # acknowledge|dismiss|escalate|mark_responded|add_note
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id = Column(Integer, primary_key=True)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    kind = Column(String(64), nullable=False)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)


class DeviceEvent(Base):
    __tablename__ = "device_events"
    id = Column(Integer, primary_key=True)
    device_id = Column(String(64), ForeignKey("sensor_devices.id"), nullable=False, index=True)
    event_name = Column(String(64), nullable=False)  # e.g. offline, battery_low, reconnected
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class SyncQueueRow(Base):
    """Server-side mirror of services/sync_engine/queue.py's sqlite table, for durability across
    API restarts (the edge/gateway keeps its own local copy too)."""
    __tablename__ = "sync_queue"
    event_id = Column(String(64), primary_key=True)
    payload = Column(JSON, nullable=False)
    event_ts = Column(String(64), nullable=True)
    enqueued_at = Column(DateTime(timezone=True), default=_now)
    status = Column(String(16), default="pending")
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null for system-generated
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(64), nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)
