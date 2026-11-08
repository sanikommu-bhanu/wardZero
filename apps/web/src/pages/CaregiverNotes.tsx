import React, { useEffect, useState } from "react";
import { GlassCard, GlassButton } from "../components/GlassCard";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { notesApi, patientsApi, type PatientSummary } from "../lib/api";
import { titleCase } from "../lib/format";

const LANGUAGES = [
  { value: "en", label: "English" }, { value: "hi", label: "Hindi" },
  { value: "ta", label: "Tamil" }, { value: "te", label: "Telugu" },
  { value: "hi_rom", label: "Hindi (Roman)" },
];
const NOTE_KEYS = ["breathing_difficulty", "weakness", "fever", "chest_discomfort", "dizziness", "confusion", "reduced_appetite", "abnormal_behavior"];

export default function CaregiverNotes() {
  const { push } = useToast();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [patientId, setPatientId] = useState("");
  const [language, setLanguage] = useState("en");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  useEffect(() => {
    patientsApi.list().then((p) => { setPatients(p); if (p.length) setPatientId(p[0].id); }).catch((e) => setError(e?.message || "Failed to load patients"));
  }, []);

  async function analyze() {
    if (!text.trim() || !patientId) return;
    setBusy(true);
    setResult(null);
    try {
      const note = await notesApi.analyze(patientId, text.trim(), language);
      setResult(note.result || note);
      push("Note analyzed", "success");
    } catch (e: any) {
      push(e?.message || "Failed to analyze note", "error");
    } finally {
      setBusy(false);
    }
  }

  if (error && !patients) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!patients) return <LoadingBlock rows={3} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Caregiver Notes (Multilingual AI)</div>
          <div className="page-subtitle">Free-text notes analyzed for clinically relevant signals.</div>
        </div>
      </div>

      <div className="two-col">
        <GlassCard hover={false}>
          <div className="flex flex-col gap-16">
            <div>
              <label className="field-label" htmlFor="note-patient">Patient</label>
              <select id="note-patient" className="input-field focus-ring" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
                {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label">Language</label>
              <div className="segmented">
                {LANGUAGES.map((l) => (
                  <button key={l.value} className={language === l.value ? "active" : ""} onClick={() => setLanguage(l.value)}>{l.label}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="field-label" htmlFor="note-text">Note</label>
              <textarea
                id="note-text" className="input-field focus-ring" rows={6}
                style={{ resize: "vertical", fontFamily: "inherit" }}
                placeholder="Add a note about the patient's current condition..."
                value={text} onChange={(e) => setText(e.target.value)}
              />
            </div>
            <GlassButton variant="primary" disabled={busy || !text.trim()} onClick={analyze}>{busy ? "Analyzing..." : "Analyze with AI"}</GlassButton>
          </div>
        </GlassCard>

        <GlassCard hover={false}>
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 14 }}>Extracted Insights</div>
          {!result ? (
            <div className="text-tertiary" style={{ fontSize: 13 }}>Analyze a note to see structured findings here.</div>
          ) : (
            <div className="flex flex-col gap-16">
              <div>
                <div className="text-secondary" style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.04em" }}>Findings</div>
                <div className="flex items-center gap-8" style={{ flexWrap: "wrap" }}>
                  {NOTE_KEYS.map((k) => {
                    const isPresent = result.present?.includes(k);
                    const isNegated = result.negated?.includes(k);
                    const isHistorical = result.historical?.includes(k);
                    const isUncertain = result.uncertain?.includes(k);
                    if (!isPresent && !isNegated && !isHistorical) return null;
                    const cls = isPresent ? "finding-present" : isNegated ? "finding-negated" : "finding-historical";
                    return (
                      <span key={k} className={`finding-badge ${cls}`}>
                        {titleCase(k)}{isUncertain && <span className="uncertain-mark">?</span>}
                      </span>
                    );
                  })}
                  {!NOTE_KEYS.some((k) => result.present?.includes(k) || result.negated?.includes(k) || result.historical?.includes(k)) && (
                    <span className="text-tertiary" style={{ fontSize: 12.5 }}>No clinical signals detected in this note.</span>
                  )}
                </div>
              </div>

              {Array.isArray(result.languages) && result.languages.length > 0 && (
                <div>
                  <div className="text-secondary" style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.04em" }}>Detected language(s)</div>
                  <div className="flex items-center gap-8" style={{ flexWrap: "wrap" }}>
                    {result.languages.map((l: string) => <span key={l} className="chip">{l}</span>)}
                  </div>
                </div>
              )}

              {result.disclaimer && (
                <div className="text-tertiary" style={{ fontSize: 11, borderTop: "1px solid var(--border-glass)", paddingTop: 10 }}>{result.disclaimer}</div>
              )}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
