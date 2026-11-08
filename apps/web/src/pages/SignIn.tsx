import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { GlassButton } from "../components/GlassCard";
import { AUTH_BG_URL } from "../lib/avatars";

export default function SignIn() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signIn(email.trim(), password);
      const dest = (location.state as any)?.from?.pathname || "/";
      navigate(dest, { replace: true });
    } catch (err: any) {
      setError(err?.message || "Sign in failed. Check your credentials.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-visual" style={{ backgroundImage: `url(${AUTH_BG_URL})` }}>
        <div className="auth-brand">
          <div style={{ width: 38, height: 38, borderRadius: 11, display: "grid", placeItems: "center", background: "linear-gradient(135deg, var(--bronze-soft), var(--bronze))", color: "var(--on-bronze)", fontWeight: 800, fontSize: 17 }}>W</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 17 }}>WardZero AI</div>
            <div className="text-secondary" style={{ fontSize: 12 }}>Intelligent Home-Care Monitoring</div>
          </div>
        </div>
        <div>
          <div className="auth-tagline">Care for your loved ones with confidence.</div>
          <div className="flex flex-col gap-8" style={{ marginTop: 24, fontSize: 13 }}>
            <div className="flex items-center gap-8"><span>{"\u26A1"}</span> Always aware</div>
            <div className="flex items-center gap-8"><span>{"\u26A1"}</span> Always safer</div>
          </div>
        </div>
      </div>

      <div className="auth-form-side">
        <div className="glass-panel-strong auth-card" style={{ padding: 32 }}>
          <div style={{ fontWeight: 700, fontSize: 22, marginBottom: 4 }}>Welcome back</div>
          <div className="text-secondary" style={{ fontSize: 13.5, marginBottom: 24 }}>Sign in to continue to a safer tomorrow.</div>

          <form onSubmit={onSubmit} className="flex flex-col gap-16">
            <div>
              <label className="field-label" htmlFor="email">Email address</label>
              <input id="email" type="email" required autoComplete="email" className="input-field focus-ring" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div>
              <label className="field-label" htmlFor="password">Password</label>
              <div style={{ position: "relative" }}>
                <input
                  id="password" type={showPw ? "text" : "password"} required autoComplete="current-password"
                  className="input-field focus-ring" style={{ paddingRight: 42 }}
                  value={password} onChange={(e) => setPassword(e.target.value)} placeholder={"\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"}
                />
                <button
                  type="button" className="focus-ring" aria-label={showPw ? "Hide password" : "Show password"}
                  onClick={() => setShowPw((s) => !s)}
                  style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer" }}
                >
                  {showPw ? "\u{1F441}" : "\u{1F576}"}
                </button>
              </div>
            </div>

            {error && <div className="text-tertiary" style={{ color: "var(--red-text)", fontSize: 12.5 }}>{error}</div>}

            <GlassButton type="submit" variant="primary" disabled={busy}>{busy ? "Signing in..." : "Sign In"}</GlassButton>
            <div className="text-tertiary center-col" style={{ fontSize: 12.5 }}>Forgot password? Contact your ward administrator.</div>
          </form>

          <div className="divider" />
          <div className="center-col text-secondary" style={{ fontSize: 13 }}>
            Don't have an account? <Link to="/sign-up" className="link-btn" style={{ marginLeft: 4 }}>Sign up</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
