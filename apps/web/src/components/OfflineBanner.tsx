import React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useRealtime } from "../context/RealtimeContext";

export function OfflineBanner() {
  const { wsConnected, browserOnline, lastSyncAt, queuedActions } = useRealtime();
  const degraded = !browserOnline || !wsConnected;

  return (
    <AnimatePresence>
      {degraded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          style={{ overflow: "hidden" }}
        >
          <div className="glass-panel" style={{
            margin: "10px 24px 0", padding: "10px 16px", borderColor: "var(--amber)",
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap",
          }}>
            <div className="flex items-center gap-8">
              <span className="status-dot status-amber" />
              <span style={{ fontSize: 13 }}>
                {!browserOnline ? "You're offline — showing last known data." : "Realtime connection lost — reconnecting..."}
              </span>
            </div>
            <div className="text-tertiary" style={{ fontSize: 12 }}>
              {queuedActions.length > 0 && <span>{queuedActions.length} action(s) queued · </span>}
              Last sync: {lastSyncAt ? new Date(lastSyncAt).toLocaleTimeString() : "never"}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
