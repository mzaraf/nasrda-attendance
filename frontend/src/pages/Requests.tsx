import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../api";

type Tab = "leave" | "duty" | "recurring";
type Request = { id: number; kind?: string; location?: string; start_date: string; end_date: string; off_weekdays?: number[]; reason: string; approval_state: "pending" | "approved" | "rejected" | "recalled"; approval_message: string };
const LEAVE_TYPES = [["annual", "Annual leave"], ["sick", "Sick leave"], ["casual", "Casual leave"], ["maternity", "Maternity leave"], ["paternity", "Paternity leave"], ["training", "Training"], ["study", "Study leave"], ["conference", "Conference"], ["official_travel", "Official travel"], ["permission", "Permission"], ["other", "Other"]] as const;
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const PAGE_SIZE = 5;

export default function Requests() {
  const [tab, setTab] = useState<Tab>("leave"), [requestPage, setRequestPage] = useState(1);
  const qc = useQueryClient();
  const [leave, setLeave] = useState({ kind: "annual", start_date: "", end_date: "", reason: "" });
  const [duty, setDuty] = useState({ location: "", start_date: "", end_date: "", reason: "" });
  const [recurring, setRecurring] = useState({ start_date: "", end_date: "", off_weekdays: [] as number[], reason: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const endpoint = tab === "leave" ? "/staff/leave/" : tab === "duty" ? "/staff/official-duty/" : "/staff/recurring-leave/";
  const { data: requests = [] } = useQuery({ queryKey: ["requests", tab], queryFn: () => api.get(endpoint).then((r) => r.data as Request[]) });
  const form = tab === "leave" ? leave : tab === "duty" ? duty : recurring;
  const submit = useMutation({ mutationFn: () => api.post(endpoint, form), onSuccess: () => {
    const label = tab === "leave" ? "Leave" : tab === "duty" ? "Official-duty" : "Recurring leave";
    setMsg({ ok: true, text: `${label} request submitted and is awaiting your Director's approval.` }); setRequestPage(1); qc.invalidateQueries({ queryKey: ["requests", tab] });
    if (tab === "leave") setLeave({ kind: "annual", start_date: "", end_date: "", reason: "" }); else if (tab === "duty") setDuty({ location: "", start_date: "", end_date: "", reason: "" }); else setRecurring({ start_date: "", end_date: "", off_weekdays: [], reason: "" });
  }, onError: (e) => setMsg({ ok: false, text: errorOf(e).message }) });
  const ready = !!form.start_date && !!form.end_date && (tab === "leave" || (tab === "duty" ? !!duty.location.trim() : recurring.off_weekdays.length > 0));
  const pages = Math.max(1, Math.ceil(requests.length / PAGE_SIZE));
  const visible = requests.slice((requestPage - 1) * PAGE_SIZE, requestPage * PAGE_SIZE);
  const selectTab = (next: Tab) => { setTab(next); setRequestPage(1); setMsg(null); };
  const updateDate = (field: "start_date" | "end_date", value: string) => { if (tab === "leave") setLeave({ ...leave, [field]: value }); else if (tab === "duty") setDuty({ ...duty, [field]: value }); else setRecurring({ ...recurring, [field]: value }); };
  const toggleDay = (day: number) => setRecurring((current) => ({ ...current, off_weekdays: current.off_weekdays.includes(day) ? current.off_weekdays.filter((value) => value !== day) : [...current.off_weekdays, day].sort() }));
  const heading = tab === "leave" ? "leave" : tab === "duty" ? "official duty" : "recurring leave";
  return <div className="page"><h2>Requests</h2><p className="muted">Submit leave, official-duty, or recurring part-time leave requests and follow their approval status.</p>
    <div className="row request-tabs"><button className={`btn ${tab === "leave" ? "primary" : ""}`} onClick={() => selectTab("leave")}>Leave</button><button className={`btn ${tab === "duty" ? "primary" : ""}`} onClick={() => selectTab("duty")}>Official duty</button><button className={`btn ${tab === "recurring" ? "primary" : ""}`} onClick={() => selectTab("recurring")}>Recurring leave</button></div>
    <div className="card"><h3>Request {heading}</h3>
      {tab === "leave" && <><label>Leave type</label><select value={leave.kind} onChange={(e) => setLeave({ ...leave, kind: e.target.value })}>{LEAVE_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></>}
      {tab === "duty" && <><label>Duty location</label><input value={duty.location} onChange={(e) => setDuty({ ...duty, location: e.target.value })} placeholder="e.g. Abuja field site" /></>}
      {tab === "recurring" && <><label>Weekly off days</label><p className="muted form-help">Select every day you will be off during this approved arrangement.</p><div className="weekday-options">{WEEKDAYS.map((day, index) => <label key={day} className="weekday-option"><input type="checkbox" checked={recurring.off_weekdays.includes(index)} onChange={() => toggleDay(index)} />{day}</label>)}</div></>}
      <div className="request-date-row"><div><label>Start date</label><input className="request-date-input" aria-label="Start date" type="date" value={form.start_date} onChange={(e) => updateDate("start_date", e.target.value)} /></div><div><label>End date</label><input className="request-date-input" aria-label="End date" type="date" value={form.end_date} onChange={(e) => updateDate("end_date", e.target.value)} /></div></div>
      <label>Reason</label><textarea rows={3} value={form.reason} onChange={(e) => tab === "leave" ? setLeave({ ...leave, reason: e.target.value }) : tab === "duty" ? setDuty({ ...duty, reason: e.target.value }) : setRecurring({ ...recurring, reason: e.target.value })} />
      {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}<button className="btn primary" disabled={!ready || submit.isPending} onClick={() => submit.mutate()}>{submit.isPending ? "Submitting…" : "Submit request"}</button></div>
    <h3>Your {heading} {tab === "recurring" ? "schedules" : "requests"}</h3>
    {requests.length === 0 ? <p className="muted">No requests yet.</p> : <>{visible.map((item) => <div className="row-card" key={item.id}><div><b>{tab === "leave" ? item.kind?.replaceAll("_", " ") : tab === "duty" ? item.location : `Off: ${(item.off_weekdays ?? []).map((day) => WEEKDAYS[day]).join(", ")}`}</b><small>{item.start_date} → {item.end_date}{item.reason ? ` · ${item.reason}` : ""}</small><small className={item.approval_state === "rejected" ? "status-rejected" : item.approval_state === "approved" ? "status-approved" : "muted"}>{item.approval_message}</small></div><span className={`pill ${item.approval_state}`}>{item.approval_state === "pending" ? "IN REVIEW" : item.approval_state.toUpperCase()}</span></div>)}{pages > 1 && <div className="request-pagination"><span className="muted">Page {requestPage} of {pages}</span><div><button className="btn" disabled={requestPage === 1} onClick={() => setRequestPage((page) => page - 1)}>Previous</button><button className="btn" disabled={requestPage === pages} onClick={() => setRequestPage((page) => page + 1)}>Next</button></div></div>}</>}
  </div>;
}
