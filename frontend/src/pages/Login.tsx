import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorOf } from "../api";
import { useAuth } from "../auth";

export default function Login({ onAuthenticated }: { onAuthenticated?: () => void }) {
  const { adoptSession } = useAuth();
  const navigate = useNavigate();
  const [ippis, setIppis] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/auth/login/", { ippis_number: ippis, password });
      if (data.mfa_required) { setMfaRequired(true); return; }
      // The login response is the authoritative identity for this new server session.
      // Do not invalidate `me` here: an in-flight response from the previous user can
      // otherwise overwrite this account's role permissions until the browser reloads.
      await adoptSession({ authenticated: true, ...data });
      onAuthenticated?.();
      navigate(data.mfa_enabled && !data.mfa_configured ? "/device" : "/", { replace: true });
    }
    catch (e) { setErr(errorOf(e).message); }
    finally { setBusy(false); }
  };
  const verifyMfa = async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/auth/mfa/verify/", { code: mfaCode });
      await adoptSession({ authenticated: true, ...data });
      onAuthenticated?.(); navigate("/", { replace: true });
    } catch (e) { setErr(errorOf(e).message); }
    finally { setBusy(false); }
  };
  const requestPasswordReset = async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/auth/password-reset/", { ippis_number: ippis });
      setErr(data.message);
    } catch (e) { setErr(errorOf(e).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="login">
      <div className="brand">
        <img src="/logo.png" alt="NASRDA" className="logo-img" />
        <h1>National Space Research and Development Agency</h1>
        <p>Staff Attendance System</p>
      </div>
      <div className="card">
        {mfaRequired ? <>
          <h2>Verify sign-in</h2><p className="muted">Open your authenticator app and enter the current six-digit code.</p>
          <label>Authenticator code</label><input value={mfaCode} onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" onKeyDown={(e) => e.key === "Enter" && verifyMfa()} />
          {err && <div className="alert error">{err}</div>}
          <button className="btn primary" disabled={busy || mfaCode.length !== 6} onClick={verifyMfa}>{busy ? "Verifying…" : "Verify and sign in"}</button>
          <button className="btn" disabled={busy} onClick={() => { setMfaRequired(false); setMfaCode(""); }}>Use a different account</button>
        </> : resetMode ? <>
          <h2>Reset password</h2><p className="muted">Enter your IPPIS number. A new password will be sent to the email address registered on your account.</p>
          <label>IPPIS Number</label><input value={ippis} onChange={(e) => setIppis(e.target.value)} inputMode="numeric" autoComplete="username" />
          {err && <div className={err.startsWith("A new password") ? "alert success" : "alert error"}>{err}</div>}
          <button className="btn primary" disabled={busy || !ippis} onClick={requestPasswordReset}>{busy ? "Sending…" : "Email new password"}</button>
          <button className="btn" disabled={busy} onClick={() => { setResetMode(false); setErr(""); }}>Back to sign in</button>
        </> : <>
        <label>IPPIS Number</label>
        <input value={ippis} onChange={(e) => setIppis(e.target.value)}
               inputMode="numeric" autoComplete="username" autoCapitalize="off" spellCheck={false} />

        <label>Password</label>
        <div className="password-field">
          <input type={showPassword ? "text" : "password"} value={password}
                 onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
                 onKeyDown={(e) => e.key === "Enter" && submit()} />
          <button type="button" className="eye-btn" tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((s) => !s)}>
            {showPassword ? (
              // eye-off
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.1A9.9 9.9 0 0112 5c5.5 0 9.5 4 11 7-.6 1.2-1.6 2.6-3 3.9M6.1 6.1C4.1 7.5 2.6 9.4 1 12c1.5 3 5.5 7 11 7 1.3 0 2.5-.2 3.6-.6" />
              </svg>
            ) : (
              // eye
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>

        {err && <div className="alert error">{err}</div>}
        <button className="btn primary" disabled={busy || !ippis || !password} onClick={submit}>
          {busy ? (<><span className="spinner" aria-hidden="true" /> Signing in…</>) : "Sign in"}
        </button>
        <button className="link login-reset-link" type="button" onClick={() => { setResetMode(true); setErr(""); }}>Forgot password?</button>
        </>}
      </div>
    </div>
  );
}
