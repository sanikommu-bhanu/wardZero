import React, { useEffect, useState } from "react";
import { GlassCard, GlassButton } from "../components/GlassCard";
import { LoadingBlock, ErrorBlock } from "../components/StateViews";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../lib/api";
import { initials } from "../lib/avatars";
import { SegmentedFilter } from "../components/FilterBar";
import { applyTheme, getTheme, ThemePref } from "../lib/theme";

export default function Settings() {
  const { signOut } = useAuth();
  const [me, setMe] = useState<{ id: string; email: string; role: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<ThemePref>(getTheme());

  useEffect(() => {
    authApi.me().then(setMe).catch((e) => setError(e?.message || "Failed to load account"));
  }, []);

  if (error && !me) return <ErrorBlock detail={error} onRetry={() => window.location.reload()} />;
  if (!me) return <LoadingBlock rows={2} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Settings &amp; Profile</div>
          <div className="page-subtitle">Account details from your signed-in session.</div>
        </div>
      </div>

      <GlassCard hover={false}>
        <div style={{ fontWeight: 600, marginBottom: 10 }}>Appearance</div>
        <SegmentedFilter<ThemePref> value={theme} onChange={(v) => { setTheme(v); applyTheme(v); }}
          options={[{ value: "auto", label: "Match system" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
      </GlassCard>

      <div className="two-col">
        <GlassCard hover={false}>
          <div className="flex items-center gap-16" style={{ marginBottom: 20 }}>
            <span className="avatar avatar-fallback" style={{ width: 56, height: 56, fontSize: 18 }}>{initials(me.email)}</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 17 }}>{me.email}</div>
              <div className="text-tertiary" style={{ fontSize: 12, textTransform: "capitalize" }}>{me.role}</div>
            </div>
          </div>
          <div className="text-tertiary" style={{ fontSize: 12, marginBottom: 20 }}>
            This API doesn't expose a profile-update endpoint yet, so editing name/email/photo isn't available here — showing your account as the backend reports it, rather than a form with nowhere to submit.
          </div>
          <GlassButton variant="danger" onClick={signOut}>Sign out</GlassButton>
        </GlassCard>

        <GlassCard hover={false}>
          <div style={{ fontWeight: 650, fontSize: 14, marginBottom: 12 }}>About WardZero AI</div>
          <div className="flex flex-col gap-8" style={{ fontSize: 13 }}>
            <div className="flex items-center justify-between"><span className="text-secondary">Build</span><span className="mono">Demo / synthetic data</span></div>
            <div className="flex items-center justify-between"><span className="text-secondary">Account ID</span><span className="mono">{me.id}</span></div>
          </div>
          <div className="divider" />
          <div className="text-tertiary" style={{ fontSize: 11.5 }}>
            Synthetic demo data · not a diagnosis. WardZero AI is a clinical decision-support prototype, not an emergency-response substitute.
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
