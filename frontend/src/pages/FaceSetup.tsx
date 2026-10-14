import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import FaceCapture from "../components/FaceCapture";

type Status = { status: "not_enrolled" | "active" | "revoked"; enrolled_at: string | null; last_verified_at: string | null };
const date = (value: string | null) => value ? new Intl.DateTimeFormat("en-NG", { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Lagos" }).format(new Date(value)) : "—";

export default function FaceSetup() {
  const { refresh } = useAuth(); const qc = useQueryClient(); const [enrolling, setEnrolling] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["face-status"], queryFn: () => api.get("/staff/face/").then((r) => r.data as Status) });
  if (isLoading) return <div className="page"><p className="muted">Loading…</p></div>;
  const active = data?.status === "active";
  return <div className="page"><h2>Face verification</h2><p className="muted"></p>
    <div className="card">{active ? <><b>✓ Face verification is active</b><p className="muted">Enrolled {date(data?.enrolled_at)} · last verified {date(data?.last_verified_at)}</p><p className="muted">If your appearance changes or verification repeatedly fails, ask an administrator to reset your face verification.</p></> : <><h3>Set up face verification</h3><p className="muted">Use the front camera in good lighting. You will complete three short live camera captures.</p><button className="btn primary" onClick={() => setEnrolling(true)}>Start face setup</button></>}</div>
    {enrolling && <FaceCapture mode="enrol" onClose={() => setEnrolling(false)} onComplete={() => { setEnrolling(false); qc.invalidateQueries({ queryKey: ["face-status"] }); refresh(); }} />}
  </div>;
}
