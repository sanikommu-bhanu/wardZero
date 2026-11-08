import React, { useEffect, useState } from "react";
import { GlassCard, GlassButton } from "../components/GlassCard";
import { RiskBadge } from "../components/StatusIndicator";
import { Timeline } from "../components/Timeline";
import { AIExplanation } from "../components/AIExplanation";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { reportsApi, patientsApi, type PatientSummary } from "../lib/api";
import { clock, titleCase } from "../lib/format";

export default function Reports() {
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [patientId, setPatientId] = useState("");
  const [report, setReport] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [pdfState, setPdfState] = useState<"idle" | "loading" | "error">("idle");

  useEffect(() => {
    patientsApi.list().then((p) => { setPatients(p); if (p.length) setPatientId(p[0].id); }).catch((e) => setError(e?.message || "Failed to load patients"));
  }, []);

  useEffect(() => {
    if (!patientId) return;
    setLoadingReport(true);
    reportsApi.get(patientId).then(setReport).catch((e) => setError(e?.message || "Failed to load report")).finally(() => setLoadingReport(false));
  }, [patientId]);

  function downloadJson() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `wardzero-report-${patientId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadPdf() {
    if (!report) return;
    setPdfState("loading");
    try {
      await reportsApi.downloadPdf(patientId, report.patient?.full_name);
      setPdfState("idle");
    } catch (e: any) {
      setError(e?.message || "Failed to generate PDF");
      setPdfState("error");
    }
  }

  if (error && !patients) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!patients) return <LoadingBlock rows={3} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Reports</div>
          <div className="page-subtitle">Structured report assembled from real backend state — export as JSON or a formatted PDF.</div>
        </div>
        <select className="input-field focus-ring" style={{ maxWidth: 260 }} value={patientId} onChange={(e) => setPatientId(e.target.value)} aria-label="Select patient">
          {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
        </select>
      </div>

      {loadingReport || !report ? <LoadingBlock rows={4} /> : (
        <GlassCard hover={false}>
          <div className="flex items-center justify-between" style={{ marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 17 }}>{report.patient.full_name}</div>
              <div className="text-tertiary" style={{ fontSize: 12 }}>Generated {clock(report.generated_at)}</div>
            </div>
            <div className="flex items-center gap-8">
              <RiskBadge level={report.patient.risk_level} />
              <GlassButton size="sm" onClick={downloadJson}>Export JSON</GlassButton>
              <GlassButton size="sm" variant="primary" onClick={downloadPdf} disabled={pdfState === "loading"}>
                {pdfState === "loading" ? "Generating…" : "Download PDF"}
              </GlassButton>
            </div>
          </div>

          <div className="divider" />
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 10 }}>AI Risk Assessment</div>
          <AIExplanation assessment={report.risk_assessment} />

          <div className="divider" />
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 10 }}>Timeline</div>
          <Timeline events={report.timeline || []} />

          <div className="divider" />
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 10 }}>Alert History ({(report.alerts || []).length})</div>
          {(report.alerts || []).length === 0 ? (
            <div className="text-tertiary" style={{ fontSize: 13 }}>No alerts recorded for this patient.</div>
          ) : (
            <div className="flex flex-col gap-8">
              {report.alerts.map((a: any) => (
                <div key={a.id} className="flex items-center justify-between" style={{ fontSize: 13, borderBottom: "1px solid var(--border-glass)", paddingBottom: 8 }}>
                  <span>{titleCase(a.alert_type)}</span>
                  <span className="chip">{titleCase(a.status)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="divider" />
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 10 }}>Caregiver Notes ({(report.notes || []).length})</div>
          {(report.notes || []).length === 0 ? (
            <div className="text-tertiary" style={{ fontSize: 13 }}>No caregiver notes recorded for this patient.</div>
          ) : (
            <div className="flex flex-col gap-8">
              {report.notes.map((n: any) => <div key={n.id} style={{ fontSize: 13 }}>{n.text}</div>)}
            </div>
          )}

          <div className="text-tertiary" style={{ fontSize: 11, marginTop: 16, borderTop: "1px solid var(--border-glass)", paddingTop: 10 }}>{report.disclaimer}</div>
        </GlassCard>
      )}
    </div>
  );
}

