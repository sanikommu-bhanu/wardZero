import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PatientCard } from "../components/PatientCard";
import { FilterBar } from "../components/FilterBar";
import { LoadingBlock, ErrorBlock, EmptyBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { patientsApi, type PatientSummary } from "../lib/api";

type RiskFilter = "all" | "high" | "medium" | "low";

export default function Patients() {
  const navigate = useNavigate();
  const { subscribe } = useRealtime();
  const [searchParams, setSearchParams] = useSearchParams();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [risk, setRisk] = useState<RiskFilter>("all");
  const q = searchParams.get("q") || "";

  const load = useCallback(async () => {
    try {
      const p = await patientsApi.list();
      setPatients(p);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load patients");
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => subscribe(() => load()), [subscribe, load]);

  const counts = useMemo(() => {
    const c = { all: 0, high: 0, medium: 0, low: 0 };
    (patients || []).forEach((p) => {
      c.all += 1;
      const lvl = (p.risk_level || "").toLowerCase();
      if (lvl === "high") c.high += 1;
      else if (lvl === "medium") c.medium += 1;
      else if (lvl === "low") c.low += 1;
    });
    return c;
  }, [patients]);

  const filtered = useMemo(() => {
    let list = patients || [];
    if (risk !== "all") list = list.filter((p) => (p.risk_level || "").toLowerCase() === risk);
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      list = list.filter((p) => p.full_name.toLowerCase().includes(needle) || p.conditions.some((c) => c.toLowerCase().includes(needle)));
    }
    return list;
  }, [patients, risk, q]);

  if (error && !patients) return <ErrorBlock detail={error} onRetry={load} />;
  if (!patients) return <LoadingBlock rows={5} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Patients</div>
          <div className="page-subtitle">{counts.all} patients under monitoring</div>
        </div>
      </div>

      <FilterBar
        segment={risk}
        onSegmentChange={setRisk}
        segmentOptions={[
          { value: "all", label: `All (${counts.all})` },
          { value: "high", label: `High Risk (${counts.high})` },
          { value: "medium", label: `Medium Risk (${counts.medium})` },
          { value: "low", label: `Stable (${counts.low})` },
        ]}
        search={q}
        onSearchChange={(v) => setSearchParams(v ? { q: v } : {})}
        searchPlaceholder="Search patients or conditions..."
      />

      {filtered.length === 0 ? (
        <EmptyBlock title="No patients match this filter" detail="Try a different risk level or search term." />
      ) : (
        <div className="grid grid-cols-3">
          {filtered.map((p) => <PatientCard key={p.id} patient={p} onClick={() => navigate(`/patients/${p.id}`)} />)}
        </div>
      )}
    </div>
  );
}
