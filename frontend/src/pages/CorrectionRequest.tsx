import { useState } from "react";
import { api, errorOf } from "../api";

export default function CorrectionRequest({ recordId, onDone }: { recordId: number; onDone: () => void }) {
  const [field, setField] = useState<"check_in_at" | "check_out_at">("check_out_at");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setMsg(null);
    try {
      await api.post("/attendance/correction/", { record: recordId, field, requested_value: value, reason });
      setMsg({ ok: true, text: "Correction request submitted for approval." });
      onDone();
    } catch (e) { setMsg({ ok: false, text: errorOf(e).message }); }
    finally { setBusy(false); }
  };

  return (
    <div className="card">
      <h3>Request a correction</h3>
      <label>Which time?</label>
      <select value={field} onChange={(e) => setField(e.target.value as any)}>
        <option value="check_in_at">Check-in time</option>
        <option value="check_out_at">Check-out time</option>
      </select>
      <label>Correct time</label>
      <input type="datetime-local" value={value} onChange={(e) => setValue(e.target.value)} />
      <label>Reason</label>
      <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
      {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}
      <button className="btn primary" disabled={busy || !value || !reason} onClick={submit}>
        {busy ? "Submitting…" : "Submit request"}
      </button>
    </div>
  );
}