import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../../api";

type Holiday = { id: number; date: string; name: string; kind: "public" | "nasrda" | "non_working" | "special_working" };
const KINDS: [Holiday["kind"], string][] = [
  ["public", "Public holiday"], ["nasrda", "NASRDA holiday"], ["non_working", "Other non-working day"], ["special_working", "Special working day"],
];
const formatDate = (value: string) => value ? new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short", year: "numeric" }).format(new Date(`${value}T00:00:00`)) : "Select date";
const openNativePicker = (button: HTMLButtonElement) => {
  const input = button.parentElement?.querySelector("input") as (HTMLInputElement & { showPicker?: () => void }) | null;
  if (!input) return;
  if (input.showPicker) input.showPicker();
  else { input.focus(); input.click(); }
};

export default function Holidays() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Holiday | null>(null);
  const [creating, setCreating] = useState(false);
  const { data: holidays = [] } = useQuery({ queryKey: ["holidays"], queryFn: () => api.get("/admin/holidays/").then((r) => r.data as Holiday[]) });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/admin/holidays/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holidays"] }),
  });

  return <div className="page wide">
    <h2>Holidays and working days</h2>
    <button className="btn primary holiday-add" onClick={() => setCreating(true)}>+ Add holiday</button>
    <div className="table-wrap holidays-table">
      <table><thead><tr><th>Date</th><th>Name</th><th>Type</th><th></th></tr></thead><tbody>
        {holidays.map((holiday) => <tr key={holiday.id}><td>{new Date(`${holiday.date}T00:00:00`).toLocaleDateString("en-NG", { day: "numeric", month: "short", year: "numeric" })}</td><td>{holiday.name}</td><td>{KINDS.find(([value]) => value === holiday.kind)?.[1] ?? holiday.kind}</td><td><button className="link" onClick={() => setEditing(holiday)}>Edit</button><button className="link" onClick={() => { if (confirm(`Delete ${holiday.name}?`)) remove.mutate(holiday.id); }}>Delete</button></td></tr>)}
        {holidays.length === 0 && <tr><td colSpan={4} className="muted">No holiday dates have been added yet.</td></tr>}
      </tbody></table>
    </div>
    {(creating || editing) && <HolidayModal holiday={editing} onClose={() => { setCreating(false); setEditing(null); }} />}
  </div>;
}

function HolidayModal({ holiday, onClose }: { holiday: Holiday | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ date: holiday?.date ?? "", name: holiday?.name ?? "", kind: holiday?.kind ?? "public" as Holiday["kind"] });
  const [message, setMessage] = useState("");
  const save = useMutation({
    mutationFn: () => holiday ? api.patch(`/admin/holidays/${holiday.id}/`, form) : api.post("/admin/holidays/", form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["holidays"] }); onClose(); },
    onError: (error) => setMessage(errorOf(error).message),
  });
  return <div className="sheet-backdrop" onClick={onClose}><div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520, margin: "0 auto" }}>
    <h3>{holiday ? "Edit holiday" : "Add holiday"}</h3>
    <label>Date</label><div className="date-picker-shell"><button type="button" className={`date-picker-display${form.date ? "" : " placeholder"}`} onClick={(e) => openNativePicker(e.currentTarget)}>{formatDate(form.date)}</button><input aria-label="Holiday date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></div>
    <label>Name</label><input value={form.name} placeholder="e.g. Independence Day" onChange={(e) => setForm({ ...form, name: e.target.value })} />
    <label>Day type</label><select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as Holiday["kind"] })}>{KINDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    <small className="muted">Special working days require normal attendance, even if they fall on a weekend or holiday.</small>
    {message && <div className="alert error">{message}</div>}
    <button className="btn primary" disabled={!form.date || !form.name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save holiday"}</button>
    <button className="btn" onClick={onClose}>Cancel</button>
  </div></div>;
}
