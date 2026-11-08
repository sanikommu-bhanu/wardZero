import React from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./components/Toast";
import { RealtimeProvider } from "./context/RealtimeContext";
import { AppShell } from "./components/AppShell";
import { CommandPalette } from "./components/CommandPalette";
import { LoadingBlock } from "./components/StateViews";

import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import Dashboard from "./pages/Dashboard";
import Patients from "./pages/Patients";
import PatientDetail from "./pages/PatientDetail";
import LiveMonitor from "./pages/LiveMonitor";
import DigitalTwin from "./pages/DigitalTwin";
import AIRisk from "./pages/AIRisk";
import Alerts from "./pages/Alerts";
import IoTSimulator from "./pages/IoTSimulator";
import CaregiverNotes from "./pages/CaregiverNotes";
import Analytics from "./pages/Analytics";
import Caregivers from "./pages/Caregivers";
import Devices from "./pages/Devices";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import SystemHealth from "./pages/SystemHealth";

function FullPageLoading() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: 320 }}><LoadingBlock rows={3} /></div>
    </div>
  );
}

/** Gate for the whole app shell: unauthenticated visitors are bounced to /sign-in, remembering where
 *  they were headed so SignIn.tsx can send them back after a successful sign-in. */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullPageLoading />;
  if (!user) return <Navigate to="/sign-in" replace state={{ from: location }} />;
  return <>{children}</>;
}

/** Signed-in users shouldn't see the auth screens again — send them straight to the dashboard. */
function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <FullPageLoading />;
  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/sign-in" element={<PublicOnly><SignIn /></PublicOnly>} />
      <Route path="/sign-up" element={<PublicOnly><SignUp /></PublicOnly>} />

      <Route path="/" element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="patients" element={<Patients />} />
        <Route path="patients/:id" element={<PatientDetail />} />
        <Route path="live-monitor" element={<LiveMonitor />} />
        <Route path="digital-twin" element={<DigitalTwin />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="ai-risk" element={<AIRisk />} />
        <Route path="iot-simulator" element={<IoTSimulator />} />
        <Route path="caregiver-notes" element={<CaregiverNotes />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="caregivers" element={<Caregivers />} />
        <Route path="devices" element={<Devices />} />
        <Route path="reports" element={<Reports />} />
        <Route path="system-health" element={<SystemHealth />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
            <RealtimeProvider>
              <CommandPalette />
              <AppRoutes />
            </RealtimeProvider>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
