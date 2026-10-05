import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, errorOf } from "../../api";

type Settings = {
  work_start: string; work_end: string; checkin_late_after: string; checkin_closes_after: string; checkout_allowed_after: string; nursing_mother_checkout_after: string;
  grace_minutes: number; overtime_after_minutes: number;
  min_accuracy_m: number; max_speed_mps: number; max_devices: number;
  require_passkey: boolean; device_approval_required: boolean;
};

export default function Settings() {
  const { data, isLoading } = useQuery({ queryKey: ["settings"], queryFn: () => api.get("/admin/settings/").then((r) => r.data as Settings) });
  const [form, setForm] = useState<Settings | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (data) setForm(data); }, [data]);
  if (isLoading || !form) return <div className="page"><p className="muted">Loading settings…</p></div>;
  const set = (key: keyof Settings) => (e: any) => {
    const value = typeof form[key] === "boolean" ? e.target.checked : typeof form[key] === "number" ? Number(e.target.value) : e.target.value;
    setForm({ ...form, [key]: value });
  };
  const save = async () => {
    setSaving(true); setMsg(null);
    try { const { data: saved } = await api.patch("/admin/settings/", form); setForm(saved); setMsg({ ok: true, text: "System settings saved." }); }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); }
    finally { setSaving(false); }
  };
  return <div className="page wide">
    <h2>System settings</h2><p className="muted">Changes take effect immediately across attendance, location checks, and device security.</p>
    <section className="card"><h3>Working hours</h3><div className="row"><div><label>Work starts</label><input type="time" value={form.work_start} onChange={set("work_start")} /></div><div><label>Work ends</label><input type="time" value={form.work_end} onChange={set("work_end")} /></div></div><label>Late check-in starts at</label><input type="time" value={form.checkin_late_after} onChange={set("checkin_late_after")} /><small className="muted">Staff who check in from this time until check-in closes are marked late.</small><label>Check-in closes at</label><input type="time" value={form.checkin_closes_after} onChange={set("checkin_closes_after")} /><small className="muted">After this time, check-in is disabled and staff without an approved exception are counted absent.</small><label>Check-out available from</label><input type="time" value={form.checkout_allowed_after} onChange={set("checkout_allowed_after")} /><label>Nursing mother check-out available from</label><input type="time" value={form.nursing_mother_checkout_after} onChange={set("nursing_mother_checkout_after")} /><small className="muted">Applies only to staff marked as a nursing mother.</small><NumberField label="Overtime begins after (minutes)" value={form.overtime_after_minutes} onChange={set("overtime_after_minutes")} /></section>
    <section className="card"><h3>Location validation</h3><div className="row"><NumberField label="Required GPS accuracy (metres)" value={form.min_accuracy_m} onChange={set("min_accuracy_m")} /><NumberField label="Maximum travel speed (m/s)" value={form.max_speed_mps} onChange={set("max_speed_mps")} /></div></section>
    <section className="card"><h3>Device security</h3><NumberField label="Maximum registered devices per staff member" value={form.max_devices} onChange={set("max_devices")} /><Toggle label="Require biometric passkey for attendance" checked={form.require_passkey} onChange={set("require_passkey")} /><Toggle label="Require administrator approval for new devices" checked={form.device_approval_required} onChange={set("device_approval_required")} /></section>
    {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}<button className="btn primary" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save settings"}</button>
  </div>;
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (e: any) => void }) { return <div><label>{label}</label><input type="number" min="0" value={value} onChange={onChange} /></div>; }
function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (e: any) => void }) { return <label className="row" style={{ alignItems: "center" }}><input type="checkbox" checked={checked} onChange={onChange} style={{ width: 20 }} /><span>{label}</span></label>; }
