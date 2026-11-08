"""Tests for apps/api/reports_pdf.py — added this session.

reportlab and pypdf are both installed in this sandbox (they were not in earlier sessions on this
project — see STATUS.md), so unlike most of apps/api/ this module is fully exercised here, not just
syntax-checked: we render a realistic fixture report and then parse the resulting PDF bytes back out
with pypdf to assert the real content is present, not just that rendering didn't raise.

Word-wrapped phrases (e.g. "Escalate To" / "Doctor" landing on separate lines in a narrow table cell)
are a real PDF-layout artifact, not missing content, so assertions below normalize whitespace
(collapsing newlines to single spaces) before substring checks rather than asserting on multi-word
phrases that could legitimately wrap.
"""
import io
import re
import unittest

import pypdf

from apps.api.reports_pdf import render_patient_report_pdf


def _fixture_report(**overrides) -> dict:
    report = {
        "patient": {
            "id": "demo-ravi-kumar", "full_name": "Ravi Kumar", "age": 67,
            "is_synthetic_demo": True, "conditions": ["Hypertension", "Diabetes"],
            "risk_level": "HIGH", "risk_probability": 0.87,
        },
        "risk_assessment": {
            "risk_level": "HIGH", "probability": 0.87, "method": "model",
            "explanation": "Risk assessed as HIGH driven by falling SpO2 and rising heart rate.",
            "contributing_factors": [
                {"feature": "spo2_mean", "value": 88.0, "contribution": 0.31, "direction": "increases_risk"},
                {"feature": "heart_rate_max", "value": 118.0, "contribution": 0.22, "direction": "increases_risk"},
            ],
            "forecast": {"deterioration_24h_probability": 0.62, "deterioration_48h_probability": 0.41,
                        "basis": "binary classifiers (shap-explained)", "explanation_method": "shap"},
            "hard_threshold_breaches": [{"vital": "spo2", "value": 88, "band": "critical", "severity": "high"}],
            "recommended_escalation": "escalate_to_doctor",
        },
        "timeline": [
            {"id": 1, "kind": "reading_received", "detail": {"event_id": "e1"},
             "ts": "2026-09-27T09:00:00+00:00"},
            {"id": 2, "kind": "risk_assessed", "detail": {"risk_level": "HIGH"},
             "ts": "2026-09-27T09:00:05+00:00"},
        ],
        "alerts": [
            {"id": 1, "alert_type": "risk_deterioration", "severity": "high", "status": "ALERTED",
             "detected_at": "2026-09-27T09:00:35+00:00", "acknowledged_by": None},
        ],
        "notes": [{"text": "Patient reports mild breathlessness.", "created_at": "2026-09-27T08:55:00+00:00"}],
        "device_events": [{"ts": "2026-09-27T08:50:00+00:00", "event": "sensor_reconnected"}],
        "generated_at": "2026-09-27T09:05:00+00:00",
        "disclaimer": "Clinical decision-support prototype — not a medical diagnosis or "
                     "emergency-response substitute.",
    }
    report.update(overrides)
    return report


def _extract_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    raw = " ".join(page.extract_text() for page in reader.pages)
    return re.sub(r"\s+", " ", raw)  # collapse newlines/wrapping so phrase checks are layout-independent


class TestReportPdf(unittest.TestCase):
    def setUp(self):
        self.report = _fixture_report()
        self.pdf_bytes = render_patient_report_pdf(self.report)
        self.text = _extract_text(self.pdf_bytes)

    def test_returns_real_pdf_bytes(self):
        self.assertTrue(self.pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(self.pdf_bytes), 1000)

    def test_patient_identity_present(self):
        for expected in ("Ravi Kumar", "Age 67", "Hypertension", "Diabetes", "demo-ravi-kumar"):
            self.assertIn(expected, self.text)

    def test_synthetic_disclaimer_present(self):
        self.assertIn("SYNTHETIC DEMO PATIENT", self.text)
        self.assertIn("Clinical decision-support prototype", self.text)

    def test_risk_assessment_content_present(self):
        for expected in ("HIGH", "SHAP", "Escalate", "Doctor",
                         "falling SpO2 and rising heart rate"):
            self.assertIn(expected, self.text)

    def test_hard_threshold_breach_present(self):
        self.assertIn("Critical", self.text)
        self.assertIn("Spo2", self.text)

    def test_contributing_factors_present(self):
        self.assertIn("Spo2 Mean", self.text)
        self.assertIn("Heart Rate Max", self.text)
        self.assertIn("increases risk", self.text)

    def test_forecast_percentages_present(self):
        self.assertIn("62%", self.text)
        self.assertIn("41%", self.text)

    def test_timeline_alerts_notes_present(self):
        self.assertIn("Reading Received", self.text)
        self.assertIn("Risk Deterioration", self.text)
        self.assertIn("mild breathlessness", self.text)

    def test_no_risk_assessment_shows_honest_empty_state(self):
        report = _fixture_report(risk_assessment=None)
        text = _extract_text(render_patient_report_pdf(report))
        self.assertIn("No AI risk assessment has been recorded", text)

    def test_no_alerts_or_notes_show_honest_empty_states(self):
        report = _fixture_report(alerts=[], notes=[], timeline=[])
        text = _extract_text(render_patient_report_pdf(report))
        self.assertIn("No alerts recorded", text)
        self.assertIn("No caregiver notes recorded", text)
        self.assertIn("No timeline events recorded", text)

    def test_rules_fallback_method_labeled_honestly(self):
        report = _fixture_report()
        report["risk_assessment"] = dict(report["risk_assessment"], method="rules")
        text = _extract_text(render_patient_report_pdf(report))
        self.assertIn("Rules-based fallback", text)


if __name__ == "__main__":
    unittest.main()
