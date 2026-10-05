import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
// Temporarily disabled: retain CorrectionRequest.tsx for re-enabling later.
// import CorrectionRequest from "./CorrectionRequest";

const t = (iso?: string) =>
  iso ? new Intl.DateTimeFormat("en-NG", { hour: "numeric", minute: "2-digit", timeZone: "Africa/Lagos" }).format(new Date(iso)) : "—";
const displayMonth = (value: string) => new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(new Date(`${value}-01T00:00:00`));
const openNativePicker = (button: HTMLButtonElement) => {
  const input = button.parentElement?.querySelector("input") as (HTMLInputElement & { showPicker?: () => void }) | null;
  if (!input) return;
  if (input.showPicker) input.showPicker();
  else { input.focus(); input.click(); }
};

export default function History() {
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  // Temporarily disabled: staff correction requests from History.
  // const [selectedRecord, setSelectedRecord] = useState<number | null>(null);
  const { data = [], isLoading } = useQuery({
    queryKey: ["history", month],
    queryFn: () => api.get("/attendance/history/", { params: { month } }).then((r) => r.data as any[]),
  });
  const late = data.filter((r) => r.check_in_status === "late").length;

  return (
    <div className="page">
      <h2>Attendance history</h2>
      <div className="date-picker-shell history-month-picker">
        <button type="button" className="date-picker-display" onClick={(e) => openNativePicker(e.currentTarget)}>{displayMonth(month)}</button>
        <input aria-label="Attendance month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
      </div>
      <div className="card grid2">
        <div><small>Days present</small><b>{data.length}</b></div>
        <div><small>Late days</small><b>{late}</b></div>
      </div>
      {isLoading && <p className="muted">Loading…</p>}
      {!isLoading && data.length === 0 && <p className="muted">No records for this month.</p>}
      {data.map((r) => (
        <div className="row-card" key={r.id}>
          <div>
            <b>{new Date(r.date).toLocaleDateString("en-NG", { weekday: "short", day: "numeric", month: "short" })}</b>
            <small>{t(r.check_in_at)} → {t(r.check_out_at)} · {r.activity_count} activities</small>
          </div>
          <div><span className={`pill ${r.check_in_status}`}>{r.check_in_status === "late" ? "LATE" : "ON TIME"}</span>{/* Temporarily disabled: <button className="btn correction-btn" onClick={() => setSelectedRecord(r.id)}>Request correction</button> */}</div>
        </div>
      ))}
      {/* Temporarily disabled: correction-request modal. */}
    </div>
  );
}
