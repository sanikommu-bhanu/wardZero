import React from "react";
import { pct, titleCase } from "../lib/format";

// Renders a risk_assessment dict exactly as services/risk_engine/engine.py produces it. Every field
// is optional-safe because "method": "rules" assessments omit some model-only fields (e.g. forecast
// probabilities can be null) — we show that honestly rather than defaulting to 0%.
export function AIExplanation({ assessment }: { assessment: any }) {
  if (!assessment) {
    return <div className="text-tertiary" style={{ fontSize: 13 }}>No AI risk assessment available yet for this patient.</div>;
  }
  const factors: any[] = assessment.contributing_factors || [];
  const breaches: any[] = assessment.hard_threshold_breaches || [];

  const n2 = assessment.news2;
  return (
    <div className="flex flex-col gap-16">
      {assessment.abstained && (
        <div role="status" className="chip" style={{ borderColor: "var(--amber)", whiteSpace: "normal", padding: "8px 12px" }}>
          AI abstained: {assessment.abstain_reason || "insufficient data"}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
        <div className="glass-panel" style={{ padding: 12 }}>
          <div className="text-secondary" style={{ fontSize: 11, textTransform: "uppercase" }}>AI risk (ML)</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{assessment.abstained ? "Not computed" : titleCase(String(assessment.risk_level || "unknown"))}</div>
          {!assessment.abstained && (
            <div className="text-tertiary" style={{ fontSize: 12 }}>
              Confidence {pct(assessment.probability)} ({assessment.confidence_label || "n/a"}) · based on {assessment.n_readings_used ?? "?"} readings
            </div>
          )}
        </div>
        <div className="glass-panel" style={{ padding: 12 }}>
          <div className="text-secondary" style={{ fontSize: 11, textTransform: "uppercase" }}>NEWS2 baseline</div>
          {n2 ? (<>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{n2.score} <span style={{ fontSize: 13, fontWeight: 500 }}>({titleCase(n2.band)})</span></div>
            <div className="text-tertiary" style={{ fontSize: 12 }}>{n2.response}</div>
            <details style={{ marginTop: 6, fontSize: 12 }}>
              <summary>How this score was built</summary>
              <ul style={{ paddingLeft: 16, margin: "6px 0" }}>
                {n2.parameters.map((p: any) => <li key={p.name}>{p.name}: {String(p.value)}{p.unit ? ` ${p.unit}` : ""} → {p.points}</li>)}
              </ul>
              {n2.assumptions.map((a: string) => <div key={a} className="text-tertiary">Assumption: {a}</div>)}
            </details>
          </>) : <div className="text-tertiary" style={{ fontSize: 12 }}>Not available for this assessment.</div>}
        </div>
      </div>
      <div className="flex items-center gap-8" style={{ flexWrap: "wrap" }}>
        <span className="chip chip-strong">{assessment.method === "model" ? "AI model" : "Rules engine"}</span>
        {assessment.recommended_escalation && (
          <span className="chip">Recommended: {titleCase(assessment.recommended_escalation)}</span>
        )}
      </div>

      {assessment.explanation && (
        <div>
          <div className="text-secondary" style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Why this assessment
          </div>
          <div style={{ fontSize: 13.5, lineHeight: 1.6 }}>{assessment.explanation}</div>
        </div>
      )}

      {factors.length > 0 && (
        <div>
          <div className="text-secondary" style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Contributing factors
          </div>
          <div className="flex flex-col gap-8">
            {factors.map((f, i) => (
              <div key={i} className="flex items-center justify-between" style={{ fontSize: 13 }}>
                <span>
                  {/* services/risk_engine/rules.py and ml/explainability/explain.py only ever emit
                     "increases_risk" / "decreases_risk" on contributing_factors — this used to check
                     for "worsening", which never matches, so every factor rendered as a green down
                     arrow regardless of its real direction. Fixed to match the actual backend contract. */}
                  <span style={{ color: f.direction === "increases_risk" ? "var(--red)" : "var(--green)", marginRight: 6 }}>
                    {f.direction === "increases_risk" ? "\u2191" : "\u2193"}
                  </span>
                  {titleCase(f.feature)}
                  {f.value !== undefined && <span className="text-tertiary"> · {typeof f.value === "number" ? f.value.toFixed(1) : String(f.value)}</span>}
                </span>
                {typeof f.contribution === "number" && <span className="mono text-tertiary">{pct(f.contribution)}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {breaches.length > 0 && (
        <div className="glass-panel" style={{ borderColor: "var(--red)", padding: 12 }}>
          <div style={{ fontWeight: 600, fontSize: 12.5, marginBottom: 6, color: "var(--red-text)" }}>Hard threshold breaches</div>
          <div className="flex flex-col gap-4">
            {breaches.map((b, i) => (
              <div key={i} style={{ fontSize: 12.5 }}>
                {titleCase(b.vital)}: {b.value} — outside {titleCase(b.band)} band {b.severity ? `(${b.severity})` : ""}
              </div>
            ))}
          </div>
        </div>
      )}

      {assessment.disclaimer && (
        <div className="text-tertiary" style={{ fontSize: 11, borderTop: "1px solid var(--border-glass)", paddingTop: 10 }}>
          {assessment.disclaimer}
        </div>
      )}
    </div>
  );
}
