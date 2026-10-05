import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { startRegistration } from "@simplewebauthn/browser";
import { api, errorOf } from "../api";
import { useAuth } from "../auth";

type Device = { id: number; label: string; status: "pending" | "active" | "revoked";
                registered_at: string; last_seen_at: string | null; removal_pending: boolean };

const fmtDate = (iso?: string | null) =>
  iso ? new Intl.DateTimeFormat("en-NG", { dateStyle: "medium", timeZone: "Africa/Lagos" }).format(new Date(iso)) : "Never";

export default function DeviceSetup() {
  const { me, refresh } = useAuth();
  const qc = useQueryClient();
  const [label, setLabel] = useState(() => `${me?.last_name?.trim() || "My"}'s Phone`);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);
  const [mfaSecret, setMfaSecret] = useState("");
  const [mfaUri, setMfaUri] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaBusy, setMfaBusy] = useState(false);
  // iPhone Safari may discard a page's in-memory component state while the user
  // switches to their authenticator app. Remember that enrolment is in progress
  // so returning to this tab restores the code-entry step rather than starting over.
  const [mfaSetupStarted, setMfaSetupStarted] = useState(() => sessionStorage.getItem("mfa-setup-in-progress") === "true");

  const { data: devices = [], isLoading } = useQuery({
    queryKey: ["devices"],
    queryFn: () => api.get("/staff/devices/").then((r) => r.data as Device[]),
  });
  const active = devices.find((d) => d.status === "active");
  const pending = devices.find((d) => d.status === "pending");

  const register = async () => {
    setBusy(true); setMsg(null);
    try {
      const { data: optionsJSON } = await api.post("/staff/device/register/options/");
      const credential = await startRegistration({ optionsJSON });      // biometric prompt
      const { data } = await api.post("/staff/device/register/verify/", { credential, label });
      // Update this view immediately. The normal query invalidation below still
      // refreshes from the server, but staff should never be left looking at a
      // second Register button after registration succeeds.
      qc.setQueryData<Device[]>(["devices"], (current = []) => [
        ...current.filter((device) => device.id !== data.id), data as Device,
      ]);
      setMsg({ ok: true, text: data.status === "pending"
        ? "Device registered. Waiting for administrator approval."
        : "Device registered. You can now check in." });
      refresh();
      qc.invalidateQueries({ queryKey: ["devices"] });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.name === "NotAllowedError" ? "Setup was cancelled." : errorOf(e).message });
    } finally { setBusy(false); }
  };

  const revoke = useMutation({
    mutationFn: (id: number) => api.post(`/staff/devices/${id}/revoke/`),
    onSuccess: () => { setConfirmRemove(null); setMsg({ ok: true, text: "Removal request sent. Administrator must approve it before this device is removed." }); qc.invalidateQueries({ queryKey: ["devices"] }); },
  });
  const loadMfaSetup = async () => {
    const { data } = await api.post("/staff/mfa/setup/");
    setMfaSecret(data.secret);
    setMfaUri(data.provisioning_uri);
  };
  const startMfa = async () => {
    setMfaBusy(true); setMsg(null);
    try {
      sessionStorage.setItem("mfa-setup-in-progress", "true");
      setMfaSetupStarted(true);
      await loadMfaSetup();
    }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); }
    finally { setMfaBusy(false); }
  };
  const confirmMfa = async () => {
    setMfaBusy(true); setMsg(null);
    try {
      await api.post("/staff/mfa/confirm/", { code: mfaCode });
      sessionStorage.removeItem("mfa-setup-in-progress");
      setMfaSetupStarted(false); setMfaSecret(""); setMfaUri(""); setMfaCode("");
      setMsg({ ok: true, text: "Authenticator MFA is configured and will be required at your next sign-in." }); refresh();
    }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); }
    finally { setMfaBusy(false); }
  };

  useEffect(() => {
    if (!mfaSetupStarted || !me?.mfa_enabled || me.mfa_configured || mfaSecret) return;
    setMfaBusy(true);
    loadMfaSetup().catch((e) => setMsg({ ok: false, text: errorOf(e).message })).finally(() => setMfaBusy(false));
  }, [mfaSetupStarted, me?.mfa_enabled, me?.mfa_configured, mfaSecret]);

  if (isLoading) return <div className="page"><p className="muted">Loading…</p></div>;

  return (
    <div className="page">
      <h2>Device & biometrics</h2>

      {active ? (
        <div className="card">
          <div className="row-card" style={{ padding: 0 }}>
            <div>
              <b>✅ Device already registered</b>
              <small>{active.label} · registered {fmtDate(active.registered_at)} · last used {fmtDate(active.last_seen_at)}</small>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 10 }}>
            This device is bound to your account for check-in and check-out. Nothing else to do here.
          </p>
          {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}
          {active.removal_pending ? <div className="alert warn">Device removal is awaiting administrator approval. You can continue using this device until it is approved.</div> : confirmRemove === active.id ? (
            <div className="alert warn">
              Your administrator must approve this request. Once approved, you can't check in or out until you register a new device.
              <div className="row" style={{ marginTop: 8 }}>
                <button className="btn" onClick={() => setConfirmRemove(null)}>Cancel</button>
                <button className="btn" disabled={revoke.isPending} onClick={() => revoke.mutate(active.id)}>
                  {revoke.isPending ? (<><span className="spinner" /> Sending…</>) : "Send removal request"}
                </button>
              </div>
            </div>
          ) : (
            <button className="link" onClick={() => setConfirmRemove(active.id)}>Remove this device</button>
          )}
        </div>
      ) : pending ? (
        <div className="card">
          <b>⏳ Waiting for approval</b>
          <p className="muted">
            {pending.label} was registered and is waiting for an administrator to approve it before
            you can check in.
          </p>
        </div>
      ) : (
        <>
          <p className="muted">
            Your fingerprint or face stays on your device. NASRDA only stores a secure key that proves
            it is this device.
          </p>
          <div className="card">
            <label>Device name</label>
            <input value={label} onChange={(e) => setLabel(e.target.value)} />
            {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}
            <button className="btn primary" disabled={busy} onClick={register}>
              {busy ? (<><span className="spinner" /> Registering…</>) : "Register this device"}
            </button>
          </div>
        </>
      )}
      {me?.mfa_enabled && <div className="card">
        <h3>Authenticator app MFA</h3>
        {me.mfa_configured ? <p className="done">✓ Authenticator MFA is configured for this account.</p> : mfaSecret ? <>
          <p className="muted">In Google Authenticator, Microsoft Authenticator, Authy, or another authenticator app, choose <b>Enter a setup key</b>, then use the key below. Set the code type to <b>Time based</b>.</p>
          <label>Setup key</label><input value={mfaSecret} readOnly onFocus={(e) => e.currentTarget.select()} />
          <label>Authenticator code</label><input value={mfaCode} onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" />
          <small className="muted">Setup link: {mfaUri}</small>
          <button className="btn primary" disabled={mfaBusy || mfaCode.length !== 6} onClick={confirmMfa}>{mfaBusy ? "Confirming…" : "Confirm MFA"}</button>
        </> : <>
          <p className="muted">Your administrator requires MFA for this account. Configure it now using any standard authenticator app.</p>
          <button className="btn primary" disabled={mfaBusy} onClick={startMfa}>{mfaBusy ? "Preparing…" : "Set up authenticator app"}</button>
        </>}
      </div>}
    </div>
  );
}
