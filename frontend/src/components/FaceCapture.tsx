import { useEffect, useRef, useState } from "react";
import { api, errorOf } from "../api";
import { deviceLabel, deviceToken } from "../lib/device";

type Props = { mode: "enrol" | "verify"; action?: "check-in" | "check-out"; onComplete: (verificationId?: string) => void; onClose: () => void };
const ENROL_STEPS = ["Look straight at the camera", "Turn your head slightly left", "Turn your head slightly right"];

export default function FaceCapture({ mode, action, onComplete, onClose }: Props) {
  const video = useRef<HTMLVideoElement>(null); const stream = useRef<MediaStream | null>(null);
  const [steps, setSteps] = useState<string[]>(mode === "enrol" ? ENROL_STEPS : []);
  const [challengeId, setChallengeId] = useState(""); const [images, setImages] = useState<string[]>([]);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(true);
  const close = () => { stream.current?.getTracks().forEach((track) => track.stop()); onClose(); };
  useEffect(() => { let mounted = true;
    (async () => { try {
      const camera = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "user" }, width: { ideal: 720 }, height: { ideal: 720 } }, audio: false });
      if (!mounted) { camera.getTracks().forEach((track) => track.stop()); return; }
      stream.current = camera; if (video.current) { video.current.srcObject = camera; await video.current.play(); }
      if (mode === "verify") { const { data } = await api.post("/attendance/face/challenge/", { action }); if (!mounted) return; setSteps(data.steps); setChallengeId(data.challenge_id); }
    } catch (e) { setError(e instanceof DOMException && e.name === "NotAllowedError" ? "Camera permission is required for face verification." : errorOf(e).message); }
    finally { if (mounted) setBusy(false); } })();
    return () => { mounted = false; stream.current?.getTracks().forEach((track) => track.stop()); };
  }, [action, mode]);
  const capture = async () => {
    if (!video.current || !video.current.videoWidth) return setError("Camera is still starting. Please wait.");
    const canvas = document.createElement("canvas"); canvas.width = video.current.videoWidth; canvas.height = video.current.videoHeight;
    canvas.getContext("2d")?.drawImage(video.current, 0, 0); const next = [...images, canvas.toDataURL("image/jpeg", 0.88)]; setImages(next); setError("");
    if (next.length < 3) return;
    setBusy(true);
    try {
      if (mode === "enrol") await api.post("/staff/face/enroll/", { images: next, device_token: deviceToken(), label: deviceLabel() });
      else { const { data } = await api.post("/attendance/face/verify/", { challenge_id: challengeId, images: next }); close(); onComplete(data.verification_id); return; }
      close(); onComplete();
    } catch (e) { setImages([]); setError(errorOf(e).message); }
    finally { setBusy(false); }
  };
  const step = steps[images.length] ?? "Preparing camera…";
  return <div className="sheet-backdrop" role="presentation"><div className="sheet face-sheet" role="dialog" aria-modal="true" aria-labelledby="face-title">
    <div className="grab" /><h3 id="face-title">{mode === "enrol" ? "Set up face verification" : "Verify your face"}</h3>
    <p className="muted">{mode === "enrol" ? "Your camera captures are used only to create an encrypted facial template. Photos are not retained." : "Complete the three live camera steps. Do not use a photograph, video, or another screen."}</p>
    <div className="face-preview"><video ref={video} muted playsInline /></div>
    <p className="face-step"><b>Step {Math.min(images.length + 1, 3)} of 3:</b> {step}</p>
    {error && <div className="alert error">{error}</div>}
    <div className="row"><button className="btn" disabled={busy} onClick={close}>Cancel</button><button className="btn primary" disabled={busy || !steps.length} onClick={capture}>{busy ? "Preparing…" : images.length === 2 ? "Verify now" : "Capture photo"}</button></div>
  </div></div>;
}
