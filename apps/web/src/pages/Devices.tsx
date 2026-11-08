import React, { useCallback, useEffect, useState } from "react";
import { SensorCard } from "../components/SensorCard";
import { FilterBar } from "../components/FilterBar";
import { LoadingBlock, ErrorBlock, EmptyBlock } from "../components/StateViews";
import { useRealtime } from "../context/RealtimeContext";
import { devicesApi, patientsApi, type Device, type PatientSummary } from "../lib/api";

export default function Devices() {
  const { subscribe } = useRealtime();
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [patientId, setPatientId] = useState("all");

  const load = useCallback(async () => {
    try {
      const [d, p] = await Promise.all([devicesApi.list(), patientsApi.list()]);
      setDevices(d);
      setPatients(p);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load devices");
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => subscribe(() => load()), [subscribe, load]);

  if (error && !devices) return <ErrorBlock detail={error} onRetry={load} />;
  if (!devices) return <LoadingBlock rows={4} />;

  const filtered = patientId === "all" ? devices : devices.filter((d) => d.patient_id === patientId);
  const online = devices.filter((d) => (d.connectivity || "").toLowerCase() === "online").length;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Devices</div>
          <div className="page-subtitle">{online} of {devices.length} sensors online</div>
        </div>
      </div>

      <FilterBar
        right={
          <select className="input-field focus-ring" style={{ maxWidth: 240 }} value={patientId} onChange={(e) => setPatientId(e.target.value)} aria-label="Filter by patient">
            <option value="all">All patients</option>
            {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select>
        }
      />

      {filtered.length === 0 ? (
        <EmptyBlock title="No devices found" />
      ) : (
        <div className="grid grid-cols-3">
          {filtered.map((d) => {
            const owner = patients.find((p) => p.id === d.patient_id);
            return (
              <div key={d.id}>
                <SensorCard device={d} />
                {owner && <div className="text-tertiary" style={{ fontSize: 11, marginTop: 4, marginLeft: 4 }}>{owner.full_name}</div>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
