import React from "react";
import { GlassButton } from "./GlassCard";

export function LoadingBlock({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-12">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 64, borderRadius: 14 }} />
      ))}
    </div>
  );
}

export function ErrorBlock({ title = "Something went wrong", detail, onRetry }: { title?: string; detail?: string; onRetry?: () => void }) {
  return (
    <div className="glass-panel error-state">
      <div className="error-icon">{"\u26A0"}</div>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {detail && <div className="text-tertiary" style={{ fontSize: 12.5, marginBottom: 14 }}>{detail}</div>}
      {onRetry && <GlassButton onClick={onRetry}>Retry</GlassButton>}
    </div>
  );
}

export function EmptyBlock({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="glass-panel empty-state">
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {detail && <div className="text-tertiary" style={{ fontSize: 12.5 }}>{detail}</div>}
    </div>
  );
}
