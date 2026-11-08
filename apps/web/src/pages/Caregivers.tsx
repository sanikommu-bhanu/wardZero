import React, { useEffect, useState } from "react";
import { GlassCard } from "../components/GlassCard";
import { DataTable, type Column } from "../components/DataTable";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { caregiversApi } from "../lib/api";
import { initials } from "../lib/avatars";

export default function Caregivers() {
  const [caregivers, setCaregivers] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    caregiversApi.list().then(setCaregivers).catch((e) => setError(e?.message || "Failed to load caregivers"));
  }, []);

  if (error && !caregivers) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!caregivers) return <LoadingBlock rows={3} />;

  const columns: Column<any>[] = [
    { key: "full_name", header: "Name", sortValue: (r) => r.full_name || "", render: (r) => (
      <div className="flex items-center gap-8">
        <span className="avatar avatar-fallback" style={{ width: 30, height: 30, fontSize: 11.5 }}>{initials(r.full_name)}</span>
        {r.full_name}
      </div>
    ) },
    { key: "email", header: "Email" },
    { key: "recent_actions", header: "Recent Actions", render: (r) => (
      Array.isArray(r.recent_actions) && r.recent_actions.length ? `${r.recent_actions.length} logged` : "No recent activity"
    ) },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Caregivers</div>
          <div className="page-subtitle">{caregivers.length} registered caregivers &amp; administrators</div>
        </div>
      </div>
      <GlassCard hover={false}>
        <DataTable columns={columns} rows={caregivers} keyFn={(r) => r.id} emptyLabel="No caregivers registered yet" />
      </GlassCard>
    </div>
  );
}
