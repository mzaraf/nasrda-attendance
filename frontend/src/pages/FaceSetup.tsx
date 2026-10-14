import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import FaceCapture from "../components/FaceCapture";

type Status = { status: "not_enrolled" | "active" | "revoked"; enrolled_at: string | null; last_verified_at: string | null };
type Device = { id: number; label: string; status: "pending" | "active" | "revoked"; registered_at: string; last_seen_at: string | null; removal_pending: boolean };
const date = (value: string | null) => value ? new Intl.DateTimeFormat("en-NG", { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Lagos" }).format(new Date(value)) : "—";

export default function FaceSetup() {
  const { refresh } = useAuth(); const qc = useQueryClient(); const [enrolling, setEnrolling] = useState(false); const [removing, setRemoving] = useState<number | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["face-status"], queryFn: () => api.get("/staff/face/").then((r) => r.data as Status) });
  const { data: devices = [] } = useQuery({ queryKey: ["device-bindings"], queryFn: () => api.get("/staff/devices/").then((r) => r.data as Device[]) });
  if (isLoading) return <div className="page"><p className="muted">Loading…</p></div>;
  const active = data?.status === "active";
  const activeDevice = devices.find((device) => device.status === "active");
  const canBindReplacement = active && !activeDevice;
  const requestRemoval = async () => {
    if (!activeDevice) return;
    setRemoving(activeDevice.id);
    try {
      await api.post(`/staff/devices/${activeDevice.id}/remove-request/`);
      qc.invalidateQueries({ queryKey: ["device-bindings"] });
    } finally {
      setRemoving(null);
    }
  };
  return <div className="page"><h2>Face verification</h2>
    <div className="card">{active ? <><b>✓ Face verification is active</b><p className="muted">Enrolled {date(data?.enrolled_at)} · last verified {date(data?.last_verified_at)}</p><p className="muted">If your appearance changes or verification repeatedly fails, ask an administrator to reset your face verification.</p>{activeDevice?.removal_pending ? <p className="status-rejected">Device removal is awaiting administrator approval.</p> : activeDevice ? <button className="btn" disabled={removing === activeDevice.id} onClick={requestRemoval}>{removing === activeDevice.id ? "Requesting…" : "Remove device"}</button> : canBindReplacement && <button className="btn primary" onClick={() => setEnrolling(true)}>Set up face verification on this device</button>}</> : <><h3>Set up face verification</h3><p className="muted">Use the front camera in good lighting. This also registers this browser/device automatically.</p><button className="btn primary" onClick={() => setEnrolling(true)}>Start face setup</button></>}</div>
    {enrolling && <FaceCapture mode="enrol" onClose={() => setEnrolling(false)} onComplete={() => { setEnrolling(false); qc.invalidateQueries({ queryKey: ["face-status"] }); qc.invalidateQueries({ queryKey: ["device-bindings"] }); refresh(); }} />}
  </div>;
}
