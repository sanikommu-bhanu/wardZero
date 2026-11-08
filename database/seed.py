"""Seed data — STEP 9, expanded this session (STEP 12 — frontend integration).
WRITTEN BUT NOT EXECUTED in this sandbox (see models.py docstring): sqlalchemy/bcrypt are not
installed here and there is no network access to install them, so this has been reviewed for
internal consistency but not run against a real database.

Creates one administrator, one caregiver, and twelve SYNTHETIC DEMO PATIENTS — every one flagged
is_synthetic_demo=True and carrying an explicit "not a real person" note on the profile, per spec.
`demo-ravi-kumar` is unchanged from the original seed (age 67, hypertension + diabetes) and remains
the patient apps/simulator/scenarios.py's default context is tuned for; the other eleven were added
this session purely so the frontend's Patients directory, Devices list and Analytics screens have
more than one row of real (if synthetic) data to show. Every patient gets five simulated sensor
devices (heart_rate, spo2, temperature, respiratory_rate, blood_pressure) so apps/api/frontend_routes.py
GET /devices has something real to read. Safe to re-run: every insert is guarded by an existence check.
"""
from __future__ import annotations
import os

import bcrypt

from .models import User, RoleEnum, Patient, PatientProfile, SensorDevice
from .session import get_session, init_db

DEMO_NOTE = "SYNTHETIC DEMO PATIENT — not a real person; for demonstration only."

# (id, full_name, age, conditions-dict, preferred_language)
DEMO_PATIENTS = [
    ("demo-ravi-kumar",      "Ravi Kumar",       67, dict(hypertension=True, diabetes=True), "en"),
    ("demo-lakshmi-devi",    "Lakshmi Devi",     72, dict(hypertension=True), "ta"),
    ("demo-arjun-reddy",     "Arjun Reddy",      58, dict(cardiac=True), "te"),
    ("demo-saroja-amma",     "Saroja Amma",      70, dict(copd=True), "ta"),
    ("demo-krishna-rao",     "Krishna Rao",      66, dict(post_surgery=True), "te"),
    ("demo-meena-iyer",      "Meena Iyer",       60, dict(hypertension=True), "en"),
    ("demo-suresh-babu",     "Suresh Babu",      63, dict(diabetes=True), "te"),
    ("demo-kamala-bai",      "Kamala Bai",       75, dict(copd=True), "hi"),
    ("demo-venkat-rao",      "Venkat Rao",       69, dict(cardiac=True), "te"),
    ("demo-padma-devi",      "Padma Devi",       71, dict(hypertension=True, diabetes=True), "hi"),
    ("demo-ramesh-chandra",  "Ramesh Chandra",   64, dict(post_surgery=True), "hi"),
    ("demo-anitha-kumari",   "Anitha Kumari",    59, dict(diabetes=True), "en"),
]

DEVICE_TYPES = ["heart_rate", "spo2", "temperature", "respiratory_rate", "blood_pressure"]

# Device-registry metadata for PROMPT 4 section 5. Deliberately fictitious-sounding model numbers
# ("WZ-Sim-...") rather than a real vendor's actual product name/SKU — these are simulated sensors, and
# naming them after a real manufacturer's real product would misrepresent what's actually connected.
DEVICE_REGISTRY_META = {
    "heart_rate": {"manufacturer": "WardZero Labs (simulated)", "device_model": "WZ-Sim-HR1", "firmware_version": "sim-1.0.0"},
    "spo2": {"manufacturer": "WardZero Labs (simulated)", "device_model": "WZ-Sim-PulseOx1", "firmware_version": "sim-1.0.0"},
    "temperature": {"manufacturer": "WardZero Labs (simulated)", "device_model": "WZ-Sim-Temp1", "firmware_version": "sim-1.0.0"},
    "respiratory_rate": {"manufacturer": "WardZero Labs (simulated)", "device_model": "WZ-Sim-Resp1", "firmware_version": "sim-1.0.0"},
    "blood_pressure": {"manufacturer": "WardZero Labs (simulated)", "device_model": "WZ-Sim-BP1", "firmware_version": "sim-1.0.0"},
}


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def seed():
    init_db()
    with get_session() as db:
        if not db.query(User).filter_by(email=os.environ.get("WZ_ADMIN_EMAIL", "admin@wardzero.local")).first():
            db.add(User(full_name="WardZero Admin",
                       email=os.environ.get("WZ_ADMIN_EMAIL", "admin@wardzero.local"),
                       password_hash=_hash(os.environ.get("WZ_ADMIN_PASSWORD", "change-me-on-first-run")),
                       role=RoleEnum.administrator))
        if not db.query(User).filter_by(email="caregiver.demo@wardzero.local").first():
            db.add(User(full_name="Demo Caregiver", email="caregiver.demo@wardzero.local",
                       password_hash=_hash("change-me-on-first-run"), role=RoleEnum.caregiver))
        if not db.query(User).filter_by(email="caregiver.priya@wardzero.local").first():
            db.add(User(full_name="Priya Nair", email="caregiver.priya@wardzero.local",
                       password_hash=_hash("change-me-on-first-run"), role=RoleEnum.caregiver))

        for pid, name, age, conditions, lang in DEMO_PATIENTS:
            if db.get(Patient, pid):
                continue
            db.add(Patient(id=pid, full_name=name, age=age, is_synthetic_demo=True))
            db.add(PatientProfile(patient_id=pid, preferred_language=lang, notes=DEMO_NOTE, **conditions))
            for dtype in DEVICE_TYPES:
                meta = DEVICE_REGISTRY_META[dtype]
                db.add(SensorDevice(id=f"{pid}-{dtype}", patient_id=pid, device_type=dtype,
                                    location="bedroom", is_simulated=True, status="offline",
                                    battery_pct=100, protocol="simulated",
                                    manufacturer=meta["manufacturer"], device_model=meta["device_model"],
                                    firmware_version=meta["firmware_version"]))
    print("Seed complete (or already present).")


if __name__ == "__main__":
    seed()
