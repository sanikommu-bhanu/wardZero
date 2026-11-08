import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { GlassButton } from "../components/GlassCard";
import { AUTH_BG_URL } from "../lib/avatars";

export default function SignUp() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("caregiver");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signUp(fullName.trim(), email.trim(), password, role);
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err?.message || "Sign up failed. Please try again.");
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
        <div className="auth-tagline">Join WardZero AI to make home care safer.</div>
      </div>

      <div className="auth-form-side">
        <div className="glass-panel-strong auth-card" style={{ padding: 32 }}>
          <div style={{ fontWeight: 700, fontSize: 22, marginBottom: 4 }}>Create your account</div>
          <div className="text-secondary" style={{ fontSize: 13.5, marginBottom: 24 }}>Join WardZero AI to make home care safer.</div>

          <form onSubmit={onSubmit} className="flex flex-col gap-16">
            <div>
              <label className="field-label" htmlFor="full_name">Full name</label>
              <input id="full_name" required className="input-field focus-ring" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Bhanu Shankar" />
            </div>
            <div>
              <label className="field-label" htmlFor="email">Email address</label>
              <input id="email" type="email" required autoComplete="email" className="input-field focus-ring" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div>
              <label className="field-label" htmlFor="password">Password</label>
              <div style={{ position: "relative" }}>
                <input
                  id="password" type={showPw ? "text" : "password"} required autoComplete="new-password" minLength={8}
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
            <div>
              <label className="field-label" htmlFor="role">I am a</label>
              <select id="role" className="input-field focus-ring" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="caregiver">Caregiver</option>
              </select>
            </div>

            {error && <div style={{ color: "var(--red-text)", fontSize: 12.5 }}>{error}</div>}

            <GlassButton type="submit" variant="primary" disabled={busy}>{busy ? "Creating account..." : "Create account"}</GlassButton>
          </form>

          <div className="divider" />
          <div className="center-col text-secondary" style={{ fontSize: 13 }}>
            Already have an account? <Link to="/sign-in" className="link-btn" style={{ marginLeft: 4 }}>Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
