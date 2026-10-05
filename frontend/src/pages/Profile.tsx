import { useState } from "react";
import { api, errorOf } from "../api";

export default function Profile() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const changePassword = async () => {
    if (newPassword !== confirmPassword) { setMessage({ ok: false, text: "The new password entries do not match." }); return; }
    setBusy(true); setMessage(null);
    try {
      await api.post("/auth/change-password/", { current_password: currentPassword, new_password: newPassword });
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setMessage({ ok: true, text: "Password changed successfully." });
    } catch (error) { setMessage({ ok: false, text: errorOf(error).message }); }
    finally { setBusy(false); }
  };
  return <div className="page">
    <h2>Change password</h2>
    <div className="card">
      <h3>Change password</h3>
      <p className="muted">You can choose any password you prefer.</p>
      <label>Current password</label><input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} autoComplete="current-password" />
      <label>New password</label><input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
      <label>Confirm new password</label><input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} autoComplete="new-password" />
      {message && <div className={`alert ${message.ok ? "success" : "error"}`}>{message.text}</div>}
      <button className="btn primary" disabled={busy || !currentPassword} onClick={changePassword}>{busy ? "Changing…" : "Change password"}</button>
    </div>
  </div>;
}
