import React from "react";

function Bar({ label, value, color }: { label: string; value: number | null | undefined; color: string }) {
  const has = typeof value === "number";
  return (
    <div>
      <div className="flex items-center justify-between" style={{ fontSize: 12.5, marginBottom: 5 }}>
        <span className="text-secondary">{label}</span>
        <span className="mono">{has ? `${(value! * 100).toFixed(0)}%` : "not available"}</span>
      </div>
      <div className="forecast-bar-track">
        <div className="forecast-bar-fill" style={{ width: has ? `${Math.min(100, value! * 100)}%` : "0%", background: color }} />
      </div>
    </div>
  );
}

// Forecast probabilities only exist when method === "model" (services/risk_engine). A "rules" fallback
// assessment sets these to null, which we show as "not available" — never a silent 0%, since 0% would
// misleadingly read as "no deterioration risk" rather than "no model was run".
export function ForecastChart({ forecast }: { forecast: any }) {
  if (!forecast) {
    return <div className="text-tertiary" style={{ fontSize: 13 }}>No forecast available for this patient yet.</div>;
  }
  return (
    <div className="flex flex-col gap-14">
      <Bar label="Deterioration risk — next 24h" value={forecast.deterioration_24h_probability} color="var(--amber)" />
      <Bar label="Deterioration risk — next 48h" value={forecast.deterioration_48h_probability} color="var(--red)" />
      {forecast.basis && <div className="text-tertiary" style={{ fontSize: 11.5 }}>Basis: {forecast.basis}</div>}
      {forecast.explanation_method && (
        <div className="text-tertiary" style={{ fontSize: 11 }}>Method: {forecast.explanation_method}</div>
      )}
    </div>
  );
}
