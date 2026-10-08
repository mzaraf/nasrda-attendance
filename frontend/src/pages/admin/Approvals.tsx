import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../../api";
import { useAuth } from "../../auth";

type Tab = "corrections" | "leave" | "official-duty" | "recurring-leave" | "review" | "devices" | "department-review";
type RecallTarget = { id: number; kind: "leave" | "official-duty" | "recurring-leave"; staff: string; endDate: string };
const TABS: [Tab, string][] = [/* Temporarily disabled: ["corrections", "Corrections"], */ ["leave", "Leave"],
  ["official-duty", "Official duty"], ["recurring-leave", "Recurring leave"], ["review", "Flagged for review"], ["devices", "Device removals"], ["department-review", "Department requests"]];
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Lagos" });

export default function Approvals() {
  const { me } = useAuth();
  const [tab, setTab] = useState<Tab>(me?.can_approve ? "leave" : me?.can_review_department_requests ? "department-review" : "devices");
  const [recallTarget, setRecallTarget] = useState<RecallTarget | null>(null);
  const [returnDate, setReturnDate] = useState(today());
  const [recallReason, setRecallReason] = useState("");
  const [recallError, setRecallError] = useState("");
  const qc = useQueryClient();
  const tabs = TABS.filter(([key]) => {
    if (key === "devices") return me?.can_manage_devices;
    if (key === "department-review") return !!me?.can_review_department_requests && !me?.can_approve;
    return me?.can_approve;
  });
  const listUrl = tab === "corrections" ? "/admin/corrections/"
    : tab === "leave" ? "/admin/leave/?include_active=true"
    : tab === "official-duty" ? "/admin/official-duty/?include_active=true"
    : tab === "recurring-leave" ? "/admin/recurring-leave/?include_active=true"
    : tab === "review" ? "/admin/review-queue/" : tab === "department-review" ? "/admin/department-review/" : "/admin/device-removals/";
  const { data = [] } = useQuery({ queryKey: [tab], queryFn: () => api.get(listUrl).then((r) => r.data) });
  const decide = useMutation({
    mutationFn: ({ id, decision, type }: { id: number; decision: string; type?: string }) => {
      const url = tab === "corrections" ? `/admin/corrections/${id}/decide/`
        : tab === "leave" ? `/admin/leave/${id}/decide/`
        : tab === "official-duty" ? `/admin/official-duty/${id}/decide/`
        : tab === "recurring-leave" ? `/admin/recurring-leave/${id}/decide/`
        : tab === "review" ? `/admin/review-queue/${id}/decide/` : tab === "department-review" ? `/admin/department-review/${type}/${id}/decide/` : `/admin/device-removals/${id}/decide/`;
      return api.post(url, { decision });
    }, onSuccess: () => qc.invalidateQueries({ queryKey: [tab] }),
  });
  const recall = useMutation({
    mutationFn: () => api.post(`/admin/${recallTarget!.kind}/${recallTarget!.id}/recall/`, { return_date: returnDate, reason: recallReason.trim() }),
    onSuccess: () => { setRecallTarget(null); setRecallReason(""); qc.invalidateQueries({ queryKey: [tab] }); },
    onError: (e) => setRecallError(errorOf(e).message),
  });
  const openRecall = (item: any, kind: "leave" | "official-duty" | "recurring-leave") => {
    setRecallError(""); setRecallReason(""); setReturnDate(today());
    setRecallTarget({ id: item.id, kind, staff: item.staff_name ?? item.staff, endDate: item.end_date });
  };

  return <div className="page wide">
    <h2>Approvals</h2>
    <div className="row">{tabs.map(([k, label]) => <button key={k} className={`btn ${tab === k ? "primary" : ""}`} onClick={() => setTab(k)}>{label}</button>)}</div>
    {data.length === 0 && <p className="muted">Nothing pending here.</p>}
    {data.map((item: any) => {
      const recallable = (tab === "leave" || tab === "official-duty" || tab === "recurring-leave") ? item.status === "approved" : !!item.recallable;
      const kind = tab === "recurring-leave" || item.type === "recurring-leave" ? "recurring-leave" : tab === "official-duty" || item.type === "official-duty" ? "official-duty" : "leave";
      return <div className="row-card" key={`${item.type ?? tab}-${item.id}`}>
        <div><b>{item.staff_name ?? item.staff}</b><small>
          {tab === "corrections" && `${item.field} → ${new Date(item.requested_value).toLocaleString()} — ${item.reason}`}
          {tab === "leave" && `${item.kind} · ${item.start_date} → ${item.end_date} — ${item.reason}${item.status === "approved" ? " · Approved" : ""}`}
          {tab === "official-duty" && `${item.location} · ${item.start_date} → ${item.end_date} — ${item.reason}${item.status === "approved" ? " · Approved" : ""}`}
          {tab === "recurring-leave" && `Off: ${(item.off_weekdays ?? []).map((day: number) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day]).join(", ")} · ${item.start_date} → ${item.end_date} — ${item.reason}${item.status === "approved" ? " · Approved" : ""}`}
          {tab === "review" && `${item.date} · ${item.campus} · flags: ${item.flags.join(", ") || "none"}`}
          {tab === "devices" && `${item.device_label} · IPPIS ${item.ippis} · requested ${new Date(item.requested_at).toLocaleString()}`}
          {tab === "department-review" && item.detail}
        </small></div>
        {recallable ? <button className="btn recall-btn" onClick={() => openRecall(item, kind)}>Recall</button> : <div className="row">
          <button className="btn" onClick={() => decide.mutate({ id: item.id, type: item.type, decision: tab === "review" ? "normal" : "approved" })}>{tab === "review" ? "Mark normal" : "Approve"}</button>
          <button className="btn" onClick={() => decide.mutate({ id: item.id, type: item.type, decision: tab === "review" ? "confirmed_issue" : "rejected" })}>{tab === "review" ? "Flag for HR" : "Reject"}</button>
        </div>}
      </div>;
    })}
    {recallTarget && <div className="sheet-backdrop" role="presentation" onMouseDown={() => !recall.isPending && setRecallTarget(null)}>
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="recall-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="grab" /><h3 id="recall-title">Recall {recallTarget.staff}</h3>
        <p className="muted"></p>
        <label>Return-to-duty date</label><input type="date" value={returnDate} min={today()} max={recallTarget.endDate} onChange={(e) => setReturnDate(e.target.value)} />
        <label>Reason for recall</label><textarea rows={3} value={recallReason} onChange={(e) => setRecallReason(e.target.value)} placeholder="Explain why the staff is being recalled" />
        {recallError && <div className="alert error">{recallError}</div>}
        <div className="row"><button className="btn" disabled={recall.isPending} onClick={() => setRecallTarget(null)}>Cancel</button><button className="btn primary" disabled={recall.isPending || !returnDate || !recallReason.trim()} onClick={() => recall.mutate()}>{recall.isPending ? "Recalling…" : "Confirm recall"}</button></div>
      </div>
    </div>}
  </div>;
}
