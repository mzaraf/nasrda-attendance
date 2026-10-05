import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../api";

type Tab = "leave" | "duty";
type Request = { id: number; kind?: string; location?: string; start_date: string; end_date: string; reason: string; status: string; approval_state: "pending" | "approved" | "rejected" | "recalled"; approval_message: string; created_at: string };
const LEAVE_TYPES = [["annual", "Annual leave"], ["sick", "Sick leave"], ["casual", "Casual leave"], ["maternity", "Maternity leave"], ["paternity", "Paternity leave"], ["training", "Training"], ["study", "Study leave"], ["conference", "Conference"], ["official_travel", "Official travel"], ["permission", "Permission"], ["other", "Other"]] as const;
const PAGE_SIZE = 5;
const displayDate = (value: string) => value ? new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short", year: "numeric" }).format(new Date(`${value}T00:00:00`)) : "Select date";
const openNativePicker = (button: HTMLButtonElement) => {
  const input = button.parentElement?.querySelector("input") as (HTMLInputElement & { showPicker?: () => void }) | null;
  if (!input) return;
  if (input.showPicker) input.showPicker();
  else { input.focus(); input.click(); }
};

export default function Requests() {
  const [tab, setTab] = useState<Tab>("leave");
  const [requestPage, setRequestPage] = useState(1);
  const qc = useQueryClient();
  const [leave, setLeave] = useState({ kind: "annual", start_date: "", end_date: "", reason: "" });
  const [duty, setDuty] = useState({ location: "", start_date: "", end_date: "", reason: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const endpoint = tab === "leave" ? "/staff/leave/" : "/staff/official-duty/";
  const { data: requests = [] } = useQuery({ queryKey: ["requests", tab], queryFn: () => api.get(endpoint).then((r) => r.data as Request[]) });
  const submit = useMutation({
    mutationFn: () => api.post(endpoint, tab === "leave" ? leave : duty),
    onSuccess: () => { setMsg({ ok: true, text: `${tab === "leave" ? "Leave" : "Official-duty"} request submitted and is awaiting your Director's approval.` }); setRequestPage(1); qc.invalidateQueries({ queryKey: ["requests", tab] }); if (tab === "leave") setLeave({ kind: "annual", start_date: "", end_date: "", reason: "" }); else setDuty({ location: "", start_date: "", end_date: "", reason: "" }); },
    onError: (e) => setMsg({ ok: false, text: errorOf(e).message }),
  });
  const form = tab === "leave" ? leave : duty;
  const ready = !!form.start_date && !!form.end_date && (tab === "leave" || !!duty.location.trim());
  const pageCount = Math.max(1, Math.ceil(requests.length / PAGE_SIZE));
  const visibleRequests = requests.slice((requestPage - 1) * PAGE_SIZE, requestPage * PAGE_SIZE);
  return <div className="page">
    <h2>Requests</h2><p className="muted">Submit leave or official-duty requests and follow their approval status.</p>
    <div className="row"><button className={`btn ${tab === "leave" ? "primary" : ""}`} onClick={() => { setTab("leave"); setRequestPage(1); setMsg(null); }}>Leave</button><button className={`btn ${tab === "duty" ? "primary" : ""}`} onClick={() => { setTab("duty"); setRequestPage(1); setMsg(null); }}>Official duty</button></div>
    <div className="card">
      <h3>{tab === "leave" ? "Request leave" : "Request official duty"}</h3>
      {tab === "leave" ? <><label>Leave type</label><select value={leave.kind} onChange={(e) => setLeave({ ...leave, kind: e.target.value })}>{LEAVE_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></> : <><label>Duty location</label><input value={duty.location} onChange={(e) => setDuty({ ...duty, location: e.target.value })} placeholder="e.g. Abuja field site" /></>}
      <div className="request-date-row"><div><label>Start date</label><div className="date-picker-shell"><button type="button" className={`date-picker-display${form.start_date ? "" : " placeholder"}`} onClick={(e) => openNativePicker(e.currentTarget)}>{displayDate(form.start_date)}</button><input aria-label="Start date" type="date" value={form.start_date} onChange={(e) => tab === "leave" ? setLeave({ ...leave, start_date: e.target.value }) : setDuty({ ...duty, start_date: e.target.value })} /></div></div><div><label>End date</label><div className="date-picker-shell"><button type="button" className={`date-picker-display${form.end_date ? "" : " placeholder"}`} onClick={(e) => openNativePicker(e.currentTarget)}>{displayDate(form.end_date)}</button><input aria-label="End date" type="date" value={form.end_date} onChange={(e) => tab === "leave" ? setLeave({ ...leave, end_date: e.target.value }) : setDuty({ ...duty, end_date: e.target.value })} /></div></div></div>
      <label>Reason</label><textarea rows={3} value={form.reason} onChange={(e) => tab === "leave" ? setLeave({ ...leave, reason: e.target.value }) : setDuty({ ...duty, reason: e.target.value })} />
      {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}<button className="btn primary" disabled={!ready || submit.isPending} onClick={() => submit.mutate()}>{submit.isPending ? "Submitting…" : "Submit request"}</button>
    </div>
    <h3>Your {tab === "leave" ? "leave" : "official-duty"} requests</h3>
    {requests.length === 0 ? <p className="muted">No requests yet.</p> : <>{visibleRequests.map((request) => <div className="row-card" key={request.id}><div><b>{tab === "leave" ? request.kind?.replaceAll("_", " ") : request.location}</b><small>{request.start_date} → {request.end_date}{request.reason ? ` · ${request.reason}` : ""}</small><small className={request.approval_state === "rejected" ? "status-rejected" : request.approval_state === "approved" ? "status-approved" : "muted"}>{request.approval_message}</small></div><span className={`pill ${request.approval_state}`}>{request.approval_state === "pending" ? "IN REVIEW" : request.approval_state.toUpperCase()}</span></div>)}{pageCount > 1 && <div className="request-pagination"><span className="muted">Page {requestPage} of {pageCount}</span><div><button className="btn" disabled={requestPage === 1} onClick={() => setRequestPage((page) => page - 1)}>Previous</button><button className="btn" disabled={requestPage === pageCount} onClick={() => setRequestPage((page) => page + 1)}>Next</button></div></div>}</>}
  </div>;
}
