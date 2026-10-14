import { useEffect, useState } from "react";
import { api, errorOf } from "../api";
import { useAuth } from "../auth";

/** This legacy route now exists only for optional authenticator-app MFA. */
export default function DeviceSetup() {
  const { me, refresh } = useAuth();
  const [secret, setSecret] = useState(""), [uri, setUri] = useState(""), [code, setCode] = useState("");
  const [busy, setBusy] = useState(false), [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const load = async () => { const { data } = await api.post("/staff/mfa/setup/"); setSecret(data.secret); setUri(data.provisioning_uri); };
  const start = async () => { setBusy(true); setMessage(null); try { await load(); } catch (e) { setMessage({ ok: false, text: errorOf(e).message }); } finally { setBusy(false); } };
  const confirm = async () => { setBusy(true); setMessage(null); try { await api.post("/staff/mfa/confirm/", { code }); setMessage({ ok: true, text: "Authenticator MFA is configured and will be required at your next sign-in." }); setSecret(""); setUri(""); refresh(); } catch (e) { setMessage({ ok: false, text: errorOf(e).message }); } finally { setBusy(false); } };
  useEffect(() => { if (me?.mfa_enabled && !me.mfa_configured && !secret) void start(); }, [me?.mfa_enabled, me?.mfa_configured]);
  return <div className="page"><h2>Authenticator MFA</h2><p className="muted">This uses an authenticator app for sign-in only. Attendance uses browser-camera face verification, not phone biometrics or passkeys.</p>
    {!me?.mfa_enabled ? <div className="card"><p className="muted">Authenticator MFA is not required for this account.</p></div> : me.mfa_configured ? <div className="card"><p className="done">✓ Authenticator MFA is configured.</p></div> : <div className="card">{secret ? <><p className="muted">In your authenticator app, choose <b>Enter a setup key</b>. Use this key and select <b>Time based</b>.</p><label>Setup key</label><input value={secret} readOnly onFocus={(e) => e.currentTarget.select()} /><label>Authenticator code</label><input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" /><small className="muted">Setup link: {uri}</small><button className="btn primary" disabled={busy || code.length !== 6} onClick={confirm}>{busy ? "Confirming…" : "Confirm MFA"}</button></> : <button className="btn primary" disabled={busy} onClick={start}>{busy ? "Preparing…" : "Set up authenticator app"}</button>}{message && <div className={`alert ${message.ok ? "success" : "error"}`}>{message.text}</div>}</div>}
  </div>;
}
