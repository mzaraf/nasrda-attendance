import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../../api";
import { useAuth } from "../../auth";

type Tab = "corrections" | "leave" | "official-duty" | "recurring-leave" | "review" | "devices" | "department-review";
type RecallTarget = { id: number; kind: "leave" | "official-duty" | "recurring-leave"; staff: string; endDate: string };
type RequestDetail = { item: any; kind: "leave" | "official-duty" | "recurring-leave"; directorReview: boolean };
const TABS: [Tab, string][] = [/* Temporarily disabled: ["corrections", "Corrections"], */ ["leave", "Leave"],
  ["official-duty", "Official duty"], ["recurring-leave", "Recurring leave"], ["review", "Flagged for review"], ["devices", "Device removals"], ["department-review", "Department requests"]];
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Lagos" });
const titleCase = (value?: string) => (value || "Not provided").replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const displayDate = (value?: string) => value ? new Date(`${value}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "Not provided";

export default function Approvals() {
  const { me } = useAuth();
  const [tab, setTab] = useState<Tab>(me?.can_approve ? "leave" : me?.can_review_department_requests ? "department-review" : "devices");
  const [recallTarget, setRecallTarget] = useState<RecallTarget | null>(null);
  const [returnDate, setReturnDate] = useState(today());
  const [recallReason, setRecallReason] = useState("");
  const [recallError, setRecallError] = useState("");
  const [requestDetail, setRequestDetail] = useState<RequestDetail | null>(null);
  const [comment, setComment] = useState("");
  const [decisionError, setDecisionError] = useState("");
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
    : tab === "review" ? "/admin/review-queue/" : tab === "devices" ? "/admin/device-removals/" : "/admin/department-review/";
  const { data = [] } = useQuery({ queryKey: [tab], queryFn: () => api.get(listUrl).then((r) => r.data) });
  const decide = useMutation({
    mutationFn: ({ id, decision, type, comment }: { id: number; decision: string; type?: string; comment?: string }) => {
      const url = tab === "corrections" ? `/admin/corrections/${id}/decide/`
        : tab === "leave" ? `/admin/leave/${id}/decide/`
        : tab === "official-duty" ? `/admin/official-duty/${id}/decide/`
        : tab === "recurring-leave" ? `/admin/recurring-leave/${id}/decide/`
        : tab === "review" ? `/admin/review-queue/${id}/decide/` : tab === "devices" ? `/admin/device-removals/${id}/decide/` : `/admin/department-review/${type}/${id}/decide/`;
      return api.post(url, { decision, ...(comment ? { comment } : {}) });
    }, onSuccess: () => { setRequestDetail(null); setComment(""); qc.invalidateQueries({ queryKey: [tab] }); }, onError: (e) => setDecisionError(errorOf(e).message),
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
  const openRequest = (item: any, kind: "leave" | "official-duty" | "recurring-leave") => {
    setDecisionError(""); setComment("");
    setRequestDetail({ item, kind, directorReview: tab === "department-review" });
  };

  return <div className="page wide">
    <h2>Approvals</h2>
    <div className="row">{tabs.map(([k, label]) => <button key={k} className={`btn ${tab === k ? "primary" : ""}`} onClick={() => setTab(k)}>{label}</button>)}</div>
    {data.length === 0 && <p className="muted">Nothing pending here.</p>}
    {data.map((item: any) => {
      const recallable = (tab === "leave" || tab === "official-duty" || tab === "recurring-leave") ? item.status === "approved" : !!item.recallable;
      const kind = tab === "recurring-leave" || item.type === "recurring-leave" ? "recurring-leave" : tab === "official-duty" || item.type === "official-duty" ? "official-duty" : "leave";
      const requestAwaitingDecision = !recallable && ["leave", "official-duty", "recurring-leave"].includes(kind) && (tab === "leave" || tab === "official-duty" || tab === "recurring-leave" || tab === "department-review");
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
        {recallable ? <button className="btn recall-btn" onClick={() => openRecall(item, kind)}>Recall</button> : requestAwaitingDecision ? <button className="btn approval-detail-btn" title="Review request details" aria-label="Review request details" onClick={() => openRequest(item, kind)}>✏️ Details</button> : <div className="row">
          <button className="btn" onClick={() => decide.mutate({ id: item.id, type: item.type, decision: tab === "review" ? "normal" : "approved" })}>{tab === "review" ? "Mark normal" : "Approve"}</button>
          <button className="btn" onClick={() => decide.mutate({ id: item.id, type: item.type, decision: tab === "review" ? "confirmed_issue" : "rejected" })}>{tab === "review" ? "Flag for HR" : "Reject"}</button>
        </div>}
      </div>;
    })}
    {requestDetail && <div className="sheet-backdrop" role="presentation" onMouseDown={() => !decide.isPending && setRequestDetail(null)}>
      <div className="sheet approval-detail-sheet" role="dialog" aria-modal="true" aria-labelledby="request-detail-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="grab" /><div className="approval-modal-heading"><div><p className="approval-eyebrow">REQUEST REVIEW</p><h3 id="request-detail-title">{titleCase(requestDetail.kind)} request</h3><p className="muted">Review the details, add your comment, then choose a decision.</p></div></div>
        <dl className="approval-request-summary"><div><dt>Staff member</dt><dd>{requestDetail.item.staff_name ?? requestDetail.item.staff}</dd></div>
          {requestDetail.kind === "leave" && <div><dt>Leave type</dt><dd>{titleCase(requestDetail.item.kind)}</dd></div>}
          {requestDetail.kind === "official-duty" && <div><dt>Duty location</dt><dd>{requestDetail.item.location || "Not provided"}</dd></div>}
          {requestDetail.kind === "recurring-leave" && <div><dt>Recurring off days</dt><dd>{(requestDetail.item.off_weekdays ?? []).map((day: number) => ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day]).join(", ") || "Not provided"}</dd></div>}
          <div><dt>From</dt><dd>{displayDate(requestDetail.item.start_date)}</dd></div><div><dt>To</dt><dd>{displayDate(requestDetail.item.end_date)}</dd></div>
          <div className="approval-reason"><dt>Reason</dt><dd>{requestDetail.item.reason || "No reason provided."}</dd></div>
          {requestDetail.item.supporting_document && <div className="approval-reason"><dt>Supporting document</dt><dd><a href={requestDetail.item.supporting_document} target="_blank" rel="noreferrer">Open supporting document</a></dd></div>}
        </dl>
        <label>{requestDetail.directorReview ? "Director comment" : "Administrator comment"}</label>
        <textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Enter a clear comment for the staff member" />
        {decisionError && <div className="alert error">{decisionError}</div>}
        <div className="approval-modal-actions"><button className="btn" disabled={decide.isPending} onClick={() => setRequestDetail(null)}>Cancel</button><button className="btn danger-action" disabled={decide.isPending || !comment.trim()} onClick={() => decide.mutate({ id: requestDetail.item.id, type: requestDetail.item.type, decision: "rejected", comment: comment.trim() })}>Reject request</button><button className="btn primary" disabled={decide.isPending || !comment.trim()} onClick={() => decide.mutate({ id: requestDetail.item.id, type: requestDetail.item.type, decision: "approved", comment: comment.trim() })}>{decide.isPending ? "Saving…" : "Approve request"}</button></div>
      </div>
    </div>}
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
