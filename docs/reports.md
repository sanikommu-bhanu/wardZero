# Patient reports

## Endpoints
- `GET /reports/{patient_id}` — JSON report: patient summary, full last AI risk assessment (contributing
  factors, forecast, explanation, method, hard-threshold breaches), timeline, alert history, caregiver
  notes, recent device events, disclaimer. Everything in it is read from real stored state (the
  repository, the alert store, the risk engine's last assessment) at request time — nothing is
  precomputed or cached stale.
- `GET /reports/{patient_id}/pdf` — the same data, rendered to a real PDF with `apps/api/reports_pdf.py`
  (reportlab) and returned as `application/pdf` with a `Content-Disposition: attachment` header.

## Why this exists / history
Earlier sessions on this project could not install `reportlab` (no network access in that sandbox), so
`apps/web/src/pages/Reports.tsx` deliberately did not show a "Download PDF" button — the honest choice
given the constraint, per this project's "no fake data/features" rule. `reportlab` (and `pypdf`, used
only for testing) are installed in the current sandbox, so this was implemented for real this session
and verified end-to-end (see below), not just wired up optimistically.

## What's verified vs. not
- `render_patient_report_pdf()` in `reports_pdf.py` has **no fastapi/pydantic import**, so unlike most
  of `apps/api/`, it runs in this sandbox. `tests/test_report_pdf.py` builds a realistic fixture report,
  renders it, checks the output starts with `%PDF`, and then parses the bytes back out with `pypdf` to
  assert the real patient name, the `SYNTHETIC DEMO PATIENT` banner, the risk level, contributing
  factors, a hard-threshold breach row, forecast percentages, a timeline row, an alert row, a caregiver
  note, and the disclaimer text all actually appear in the extracted text.
- The `GET /reports/{patient_id}/pdf` FastAPI route itself is a thin wrapper (build the same dict
  `patient_report()` returns, call the renderer, wrap in a `Response`) and carries the same
  "written, syntax-checked, not executed" status as every other route in `main.py` — fastapi is still
  not installed in this sandbox. The rendering logic it calls into is genuinely tested; the HTTP
  plumbing around it is not.
- The frontend button (`reportsApi.downloadPdf()` in `lib/api.ts`, wired into `Reports.tsx`) fetches the
  endpoint, reads the response as a `Blob`, and triggers a browser download via an object URL. This has
  not been exercised in an actual browser (no network access to `npm install` in this sandbox — see
  `STATUS.md`), only syntax-checked.

## Layout
Header (WardZero AI branding + synthetic-data banner) → patient info + current risk badge → AI risk
assessment (method, explanation method, recommended action, explanation text, hard-threshold breaches,
contributing factors table, 24h/48h forecast) → timeline → alert history → caregiver notes → device
events → disclaimer + generation timestamp, with a page-number footer. Every section has an explicit
honest empty state ("no alerts recorded for this patient") rather than being silently omitted or filled
with placeholder figures.

## Running it for real
On a machine with the project's dependencies actually installed (`pip install -r requirements.txt`,
which includes `reportlab`) and the API running, `curl -H "Authorization: Bearer <token>"
http://localhost:8000/reports/<patient_id>/pdf -o report.pdf` will produce a real file.
