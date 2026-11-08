# IoT (software-simulated)

No physical hardware is used or required — the challenge explicitly allows software-based IoT
simulation, and WardZero AI leans on that fully.

- `apps/simulator/simulator.py` — `PatientSimulator` emits one reading per "tick" for a patient +
  device pair, including realistic `device_state`/`connectivity` transitions (`offline`, battery,
  reconnection) so the reliability layer has real failure modes to handle, not just happy-path data.
- `apps/simulator/scenarios.py` — the same scenario catalogue used by `ml/data/generator.py`, so the
  live simulator and the training data are generated from one shared severity model, not two
  disconnected implementations.
- Each reading carries a `_true_severity` field — the ground-truth severity used only to *evaluate*
  how well the risk engine tracks reality. **This field must never reach the API's stored data or any
  response**: `apps/api/validation.py` whitelists incoming fields (an allow-list, not a strip-list) so
  `_true_severity` (and anything else unexpected) is dropped at ingestion, verified by
  `tests/test_pipeline.py::test_true_severity_never_reaches_repository`.
- Devices in `database/models.SensorDevice` are always `is_simulated=True` — there is no code path
  that talks to real hardware, and the UI must not imply otherwise (hence the synthetic-data
  disclaimers required throughout the spec).
