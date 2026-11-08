"""VALIDATE stage of the ingestion pipeline (STEP 8).

Framework-independent (no pydantic — not installed in this sandbox). apps/api/schemas.py will wrap
this with pydantic models once FastAPI is wired in, but the actual whitelist/range logic that matters
for safety lives here so it is unit-testable now.

CRITICAL (per spec): the simulator emits `_true_severity` (ground-truth label for evaluation only).
It must be stripped before the event goes anywhere downstream, and the server must whitelist allowed
fields rather than trust the sender — an allow-list, not a strip-list, so any unexpected field is
dropped rather than accidentally forwarded.
"""
from __future__ import annotations
from ml.features.schema import RANGES

ALLOWED_READING_FIELDS = {
    "event_id", "patient_id", "device_id", "timestamp", "heart_rate", "spo2", "temperature",
    "resp_rate", "systolic_bp", "diastolic_bp", "activity", "device_state", "connectivity", "scenario",
}
REQUIRED_FIELDS = {"event_id", "patient_id", "device_id", "timestamp"}
VITAL_FIELDS = set(RANGES.keys())


class ValidationResult:
    def __init__(self, ok: bool, clean: dict | None, errors: list[str]):
        self.ok = ok
        self.clean = clean
        self.errors = errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "clean": self.clean, "errors": self.errors}


def validate_event(raw: dict) -> ValidationResult:
    """Whitelist fields (dropping anything else, including `_true_severity`), check required
    fields are present, and check any present vital is within the physically plausible RANGES
    from ml.features.schema. Out-of-range vitals are dropped (set to None / omitted) and recorded
    as an error, rather than silently kept or rejecting the whole event — a sensor glitch on one
    channel should not blind us to the other channels in the same reading."""
    if not isinstance(raw, dict):
        return ValidationResult(False, None, ["event is not an object"])

    errors: list[str] = []
    clean = {k: v for k, v in raw.items() if k in ALLOWED_READING_FIELDS}

    dropped = set(raw.keys()) - ALLOWED_READING_FIELDS
    if dropped:
        errors.append(f"dropped_unrecognized_fields:{sorted(dropped)}")

    missing = REQUIRED_FIELDS - set(clean.keys())
    if missing:
        return ValidationResult(False, None, errors + [f"missing_required_fields:{sorted(missing)}"])

    for field in VITAL_FIELDS:
        if field not in clean or clean[field] is None:
            continue
        val = clean[field]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            errors.append(f"non_numeric_vital:{field}")
            clean[field] = None
            continue
        lo, hi = RANGES[field]
        if not (lo <= val <= hi):
            errors.append(f"out_of_range:{field}={val}")
            clean[field] = None

    ok = all(clean.get(f) is not None or f not in VITAL_FIELDS for f in VITAL_FIELDS) or True
    # Malformed events are still STORED (never dropped) per STEP 12 reliability requirements;
    # `ok=False` only means "some fields were rejected", tracked via `errors`, not that the whole
    # event is discarded. The caller (pipeline.ingest) decides what to do with `errors`.
    has_any_vital = any(clean.get(f) is not None for f in VITAL_FIELDS)
    ok = has_any_vital
    if not has_any_vital:
        errors.append("no_valid_vitals_present")

    return ValidationResult(ok, clean, errors)
