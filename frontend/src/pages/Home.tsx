import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, errorOf } from "../api";
import type { ApiError } from "../api";
import { useAuth } from "../auth";
import { getPosition } from "../lib/geo";
import { useOnline } from "../lib/useOnline";
import ActivitySheet from "../components/ActivitySheet";
import FaceCapture from "../components/FaceCapture";
import { deviceToken } from "../lib/device";

const fmt = (iso?: string | null) =>
  iso ? new Intl.DateTimeFormat("en-NG", { hour: "numeric", minute: "2-digit", timeZone: "Africa/Lagos" }).format(new Date(iso)) : "—";
const dur = (m?: number | null) => (m == null ? "—" : `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`);

export default function Home() {
  const { me } = useAuth();
  const qc = useQueryClient();
  const online = useOnline();
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState<ApiError | null>(null);
  const [success, setSuccess] = useState("");
  const [sheet, setSheet] = useState(false);
  const [faceAction, setFaceAction] = useState<"check-in" | "check-out" | null>(null);

  const { data } = useQuery({
    queryKey: ["today"],
    queryFn: () => api.get("/attendance/today/").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const dateStr = new Intl.DateTimeFormat("en-NG", { dateStyle: "full", timeZone: "Africa/Lagos" }).format(new Date());

  async function attend(kind: "check-in" | "check-out", faceVerificationId?: string) {
    setErr(null); setSuccess("");
    try {
      if (!online) throw { code: "OFFLINE", message: "Internet connection is required to verify and record attendance." };
      setBusy("Getting your location…");
      const fix = await getPosition();
      setBusy("Recording attendance…");
      await api.post(`/attendance/${kind}/`, { ...fix, face_verification_id: faceVerificationId, device_token: deviceToken() });
      setSuccess(kind === "check-in" ? "CHECK-IN SUCCESSFUL" : "CHECK-OUT SUCCESSFUL");
      setSheet(false);
      qc.invalidateQueries({ queryKey: ["today"] });
    } catch (e: any) {
      if (e?.name === "NotAllowedError") setErr({ code: "CANCELLED", message: "Face verification was cancelled." });
      else setErr(e?.code && e?.message && !e.response ? e : errorOf(e));
    } finally { setBusy(""); }
  }

  const rec = data?.record;
  const state: string = data?.state ?? "not_checked_in";
  const needsFace = me?.require_face_verification && !me?.face_enrolled;
  const needsDevice = me?.require_approved_device && !me?.has_approved_device;
  const checkoutAfter = data?.checkout_allowed_after ?? "16:30";
  const checkinClosesAfter = data?.checkin_closes_after ?? "12:00";
  const checkinOpen = data?.checkin_open ?? true;
  const nonWorkingReason: string | null = data?.non_working_reason ?? null;
  const serverTime = data?.server_time ? new Date(data.server_time) : null;
  const serverClock = serverTime ? new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "Africa/Lagos" }).format(serverTime) : "";
  const checkoutOpen = !!serverClock && serverClock >= checkoutAfter;

  return (
    <div className="page">
      <div className="home-grid">
        <div className="home-main">
          <header className="hero">
            <p className="muted">{dateStr}</p>
            <h2>{greeting}, {me?.first_name}</h2>
            <span className={`pill ${state}`}>
              {state === "not_checked_in" ? "Not checked in" : state === "checked_in" ? "Checked in" : "Checked out"}
            </span>
          </header>

          {!online && <div className="alert warn">You're offline. Attendance needs an internet connection.</div>}
          {nonWorkingReason && <div className="alert success">Attendance is not required today. {nonWorkingReason}</div>}
          {needsFace && (
            <div className="alert warn">
              Set up face verification to mark attendance. <Link to="/face">Set up now →</Link>
            </div>
          )}
          {needsDevice && !needsFace && <div className="alert warn">Set up face verification on this device before marking attendance. <Link to="/face">Set up now →</Link></div>}
          {me?.mfa_enabled && !me?.mfa_configured && (
            <div className="alert warn">
              Authenticator MFA is required for your account. <Link to="/device">Set it up now →</Link>
            </div>
          )}
          {success && <div className="alert success big">✓ {success}</div>}
          {err && <div className={`alert error`}>{err.message}</div>}

          <div className="action">
            {state === "not_checked_in" && !nonWorkingReason && (
              <button className="bigbtn in" disabled={!!busy || needsFace || needsDevice || !checkinOpen} onClick={() => setFaceAction("check-in")}>
                {busy || "CHECK IN"}
              </button>
            )}
            {state === "not_checked_in" && !nonWorkingReason && !checkinOpen && <small>Check-in closed at {checkinClosesAfter}. You are marked absent for today.</small>}
            {state === "not_checked_in" && nonWorkingReason && <div className="done">Office closed today</div>}
            {state === "checked_in" && (
              <button className="bigbtn out" disabled={!!busy || needsFace || needsDevice || !checkoutOpen} onClick={() => setSheet(true)}>
                {busy || "CHECK OUT"}
              </button>
            )}
            {state === "checked_in" && !checkoutOpen && <small>Check-out opens at {checkoutAfter} (Africa/Lagos time).</small>}
            {state === "checked_out" && <div className="done">Attendance complete for today 🎉</div>}
          </div>
        </div>

        <section className="card grid2 home-summary">
          <div><small>Check-in</small><b>{fmt(rec?.check_in_at)}</b></div>
          <div><small>Check-out</small><b>{fmt(rec?.check_out_at)}</b></div>
          <div><small>Duration</small><b>{dur(rec?.duration_minutes)}</b></div>
          <div><small>Campus</small><b>{rec?.campus_name ?? "—"}</b></div>
          <div><small>Status</small><b>{rec ? (rec.check_in_status === "late" ? "🔴 LATE" : "🟢 ON TIME") : "—"}</b></div>
          <div><small>Activities</small><b>{rec?.activity_count ?? 0}</b></div>
        </section>
      </div>

      {sheet && (
        <ActivitySheet
          busy={!!busy} error={err?.message}
          onClose={() => setSheet(false)}
          onSubmit={() => { setSheet(false); setFaceAction("check-out"); }}
        />
      )}
      {faceAction && <FaceCapture mode="verify" action={faceAction} onClose={() => setFaceAction(null)} onComplete={(verificationId) => { setFaceAction(null); void attend(faceAction, verificationId); }} />}
    </div>
  );
}
