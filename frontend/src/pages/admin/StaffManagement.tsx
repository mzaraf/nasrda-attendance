import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../../api";
import { useAuth } from "../../auth";

type Staff = { id: number; ippis_number: string; first_name: string; last_name: string;
               middle_name: string; email: string; phone: string; file_number: string;
               department: number | null; department_name: string; designation: string;
               grade_level: string; employment_status: string; primary_campus: number | null;
               campus_name: string; campus_policy: string; is_nursing_mother: boolean; mfa_enabled: boolean; is_active: boolean; role_ids: number[]; roles: string[] };
type Option = { id: number; name: string };
const byCampus = (departments: Option[], campusId: string | number) => !campusId ? departments : departments.filter((d: any) => d.campus_ids?.includes(Number(campusId)));

export default function StaffManagement() {
  const { me } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [importOpen, setImportOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Staff | null>(null);

  const { data: staff = [] } = useQuery({
    queryKey: ["staff", q, page],
    queryFn: () => api.get("/admin/staff/", { params: { q, page } }).then((r) => r.data),
  });
  const staffRows = Array.isArray(staff) ? staff : staff.results ?? [];
  const totalStaff = Array.isArray(staff) ? staffRows.length : staff.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalStaff / 50));

  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api.post(`/admin/staff/${id}/${active ? "deactivate" : "activate"}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["staff"] }),
  });

  return (
    <div className="page wide">
      <h2>Staff management</h2>
      <div className="staff-toolbar">
        <input className="staff-search" placeholder="Search name, IPPIS or email…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        {me?.can_manage_staff && <button className="btn" onClick={() => setImportOpen(true)}>Bulk import</button>}
        {me?.can_manage_staff && <button className="btn primary" onClick={() => setCreating(true)}>+ Add staff</button>}
      </div>

      <div className="table-wrap staff-table">
        <table>
          <thead><tr><th>IPPIS</th><th>Name</th><th>Department</th><th>Campus</th><th>Email</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {staffRows.map((s: Staff) => (
              <tr key={s.id}>
                <td>{s.ippis_number}</td><td>{s.first_name} {s.last_name}</td>
                <td>{s.department_name}</td><td>{s.campus_name}</td><td>{s.email}</td>
                <td>{s.is_active ? "🟢 Active" : "⚪ Inactive"}</td>
                <td className="row" style={{ gap: 6 }}>
                  {me?.can_manage_staff && <><button className="link" onClick={() => setEditing(s)}>Edit</button>
                    <button className="link" onClick={() => toggle.mutate({ id: s.id, active: s.is_active })}>
                      {s.is_active ? "Deactivate" : "Activate"}</button></>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalStaff > 0 && <div className="staff-pagination" aria-label="Staff directory pagination">
        <small>{totalStaff} staff · Page {page} of {totalPages}</small>
        <div>
          <button className="btn" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>Previous</button>
          <button className="btn" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>Next</button>
        </div>
      </div>}

      {importOpen && <ImportModal onClose={() => { setImportOpen(false); qc.invalidateQueries({ queryKey: ["staff"] }); }} />}
      {creating && <NewStaffModal onClose={() => { setCreating(false); qc.invalidateQueries({ queryKey: ["staff"] }); }} />}
      {editing && <EditStaffModal staff={editing} onClose={() => setEditing(null)}
                    onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["staff"] }); }} />}
    </div>
  );
}

function EditStaffModal({ staff, onClose, onSaved }: { staff: Staff; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    ippis_number: staff.ippis_number, first_name: staff.first_name, middle_name: staff.middle_name ?? "", last_name: staff.last_name,
    email: staff.email, phone: staff.phone ?? "", file_number: staff.file_number ?? "",
    department: staff.department ?? "", primary_campus: staff.primary_campus ?? "",
    campus_policy: staff.campus_policy, designation: staff.designation ?? "",
    grade_level: staff.grade_level ?? "", employment_status: staff.employment_status, role_ids: staff.role_ids ?? [],
    is_nursing_mother: staff.is_nursing_mother ?? false,
    mfa_enabled: staff.mfa_enabled ?? false,
  });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState<"password" | "devices" | null>(null);
  const [tempPassword, setTempPassword] = useState("");

  const { data: departments = [] } = useQuery({
    queryKey: ["departments"], queryFn: () => api.get("/admin/departments/").then((r) => r.data as (Option & { campus_ids?: number[] })[]),
  });
  const { data: campuses = [] } = useQuery({
    queryKey: ["campuses"], queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Option[]),
  });
  const { data: roles = [] } = useQuery({ queryKey: ["roles"], queryFn: () => api.get("/admin/roles/").then((r) => r.data as Option[]) });

  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      await api.patch(`/admin/staff/${staff.id}/`, {
        ...form, department: form.department || null, primary_campus: form.primary_campus || null,
      });
      onSaved();
    } catch (e) { setMsg({ ok: false, text: errorOf(e).message }); }
    finally { setSaving(false); }
  };

  const resetPassword = async () => {
    setResetting("password"); setMsg(null);
    try {
      const { data } = await api.post(`/admin/staff/${staff.id}/reset_password/`);
      setTempPassword(data.temporary_password);
      setMsg({ ok: true, text: data.email_sent ? "New temporary password generated and emailed to the staff member." : "New temporary password generated — hand it to the staff member directly." });
    } catch (e) { setMsg({ ok: false, text: errorOf(e).message }); }
    finally { setResetting(null); }
  };

  const resetDevices = async () => {
    if (!confirm(`Revoke all of ${staff.first_name}'s registered devices? They'll need to register a new one to check in.`)) return;
    setResetting("devices"); setMsg(null);
    try {
      const { data } = await api.post(`/admin/staff/${staff.id}/reset_devices/`);
      setMsg({ ok: true, text: `${data.revoked} device(s) revoked.` });
    } catch (e) { setMsg({ ok: false, text: errorOf(e).message }); }
    finally { setResetting(null); }
  };

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640, margin: "0 auto" }}>
        <h3>Edit staff — {staff.ippis_number}</h3>

        <label>IPPIS number</label>
        <input value={form.ippis_number} onChange={set("ippis_number")} inputMode="numeric" />
        <small className="muted">This is the staff member’s login ID. It must be unique.</small>
        <label>File number</label>
        <input value={form.file_number} onChange={set("file_number")} />
        <div className="row">
          <div><label>First name</label><input value={form.first_name} onChange={set("first_name")} /></div>
          <div><label>Last name</label><input value={form.last_name} onChange={set("last_name")} /></div>
        </div>
        <label>Middle name</label>
        <input value={form.middle_name} onChange={set("middle_name")} />
        <div className="row">
          <div><label>Email</label><input value={form.email} onChange={set("email")} /></div>
          <div><label>Phone</label><input value={form.phone} onChange={set("phone")} /></div>
        </div>

        <label>Primary campus</label>
        <select value={form.primary_campus} onChange={(e) => setForm({ ...form, primary_campus: e.target.value, department: "" })}>
          <option value="">— None —</option>
          {campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <label>Department</label>
        <select value={form.department} onChange={set("department")} disabled={!form.primary_campus}>
          <option value="">{form.primary_campus ? "— Select department —" : "— Select campus first —"}</option>
          {byCampus(departments, form.primary_campus).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>

        <label>Campus policy</label>
        <select value={form.campus_policy} onChange={set("campus_policy")}>
          <option value="one">One campus only</option>
          <option value="approved">Approved campuses</option>
          <option value="any">Any NASRDA campus</option>
        </select>

        <div className="row">
          <div><label>Designation</label><input value={form.designation} onChange={set("designation")} /></div>
          <div><label>Grade level</label><input value={form.grade_level} onChange={set("grade_level")} /></div>
        </div>
        <label>Employment status</label>
        <select value={form.employment_status} onChange={set("employment_status")}>
          <option value="permanent">Permanent</option>
          <option value="contract">Contract</option>
          <option value="nysc">NYSC</option>
          <option value="secondment">Secondment</option>
        </select>
        <label className="staff-toggle"><input type="checkbox" checked={form.is_nursing_mother} onChange={(e) => setForm({ ...form, is_nursing_mother: e.target.checked })} /><span>Nursing mother — eligible for the configured early check-out time</span></label>
        <label className="staff-toggle"><input type="checkbox" checked={form.mfa_enabled} onChange={(e) => setForm({ ...form, mfa_enabled: e.target.checked })} /><span>Require authenticator-app MFA at sign-in</span></label>

        <label>Roles</label>
        <select multiple value={form.role_ids.map(String)} onChange={(e) => setForm({ ...form, role_ids: Array.from(e.target.selectedOptions, (o) => Number(o.value)) })}>
          {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
        </select>
        <small className="muted">Hold Ctrl (or Cmd) to select multiple roles.</small>

        {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}
        {tempPassword && (
          <div className="alert warn">
            Temporary password: <b>{tempPassword}</b> — this is shown only once; copy it now.
          </div>
        )}

        <button className="btn primary" disabled={saving} onClick={save}>
          {saving ? (<><span className="spinner" /> Saving…</>) : "Save changes"}
        </button>

        <div className="row" style={{ marginTop: 14 }}>
          <button className="btn" disabled={!!resetting} onClick={resetPassword}>
            {resetting === "password" ? (<><span className="spinner" /> Resetting…</>) : "Reset password"}
          </button>
          <button className="btn" disabled={!!resetting} onClick={resetDevices}>
            {resetting === "devices" ? (<><span className="spinner" /> Revoking…</>) : "Reset devices"}
          </button>
        </div>
        <button className="btn" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}

function NewStaffModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ ippis_number: "", file_number: "", first_name: "", last_name: "", email: "", middle_name: "", phone: "", department: "", primary_campus: "", designation: "", grade_level: "", employment_status: "permanent", campus_policy: "one", is_nursing_mother: false, mfa_enabled: false, role_ids: [] as number[] });
  const [msg, setMsg] = useState("");
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const qc = useQueryClient();
  const { data: departments = [] } = useQuery({ queryKey: ["departments"], queryFn: () => api.get("/admin/departments/").then((r) => r.data as (Option & { campus_ids?: number[] })[]) });
  const { data: campuses = [] } = useQuery({ queryKey: ["campuses"], queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Option[]) });
  const { data: roles = [] } = useQuery({ queryKey: ["roles"], queryFn: () => api.get("/admin/roles/").then((r) => r.data as Option[]) });
  const create = useMutation({
    mutationFn: () => api.post("/admin/staff/", { ...form, department: form.department || null, primary_campus: form.primary_campus || null }),
    onSuccess: ({ data }) => { setTemporaryPassword(data.temporary_password); setMsg(data.email_sent ? "Staff member created and their sign-in details were emailed." : "Staff member created. Give them this temporary password securely."); qc.invalidateQueries({ queryKey: ["staff"] }); },
    onError: (e) => setMsg(errorOf(e).message),
  });
  const set = (key: string) => (e: any) => setForm({ ...form, [key]: e.target.value });
  return <div className="sheet-backdrop" onClick={onClose}><div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640, margin: "0 auto" }}>
    <h3>Add staff member</h3>
    <div className="row"><div><label>IPPIS number</label><input value={form.ippis_number} onChange={set("ippis_number")} /></div><div><label>File number</label><input value={form.file_number} onChange={set("file_number")} /></div></div>
    <div className="row"><div><label>Email</label><input type="email" value={form.email} onChange={set("email")} /></div><div><label>Phone number</label><input type="tel" value={form.phone} onChange={set("phone")} inputMode="tel" /></div></div>
    <div className="row"><div><label>First name</label><input value={form.first_name} onChange={set("first_name")} /></div><div><label>Last name</label><input value={form.last_name} onChange={set("last_name")} /></div></div>
    <label>Middle name</label><input value={form.middle_name} onChange={set("middle_name")} />
    <div className="row"><div><label>Primary campus</label><select value={form.primary_campus} onChange={(e) => setForm({ ...form, primary_campus: e.target.value, department: "" })}><option value="">— None —</option>{campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div><div><label>Department</label><select value={form.department} disabled={!form.primary_campus} onChange={set("department")}><option value="">{form.primary_campus ? "— Select department —" : "— Select campus first —"}</option>{byCampus(departments, form.primary_campus).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div></div>
    <div className="row"><div><label>Designation</label><input value={form.designation} onChange={set("designation")} /></div><div><label>Grade level</label><input value={form.grade_level} onChange={set("grade_level")} /></div></div>
    <label className="staff-toggle"><input type="checkbox" checked={form.is_nursing_mother} onChange={(e) => setForm({ ...form, is_nursing_mother: e.target.checked })} /><span>Nursing mother — eligible for the configured early check-out time</span></label>
    <label className="staff-toggle"><input type="checkbox" checked={form.mfa_enabled} onChange={(e) => setForm({ ...form, mfa_enabled: e.target.checked })} /><span>Require authenticator-app MFA at sign-in</span></label>
    <label>Roles</label><select multiple value={form.role_ids.map(String)} onChange={(e) => setForm({ ...form, role_ids: Array.from(e.target.selectedOptions, (o) => Number(o.value)) })}>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select>
    {msg && <div className={`alert ${temporaryPassword ? "success" : "error"}`}>{msg}</div>}
    {temporaryPassword && <div className="alert warn">Temporary password: <b>{temporaryPassword}</b> — shown once only.</div>}
    {!temporaryPassword && <button className="btn primary" disabled={!form.ippis_number || !form.first_name || !form.last_name || !form.email || create.isPending} onClick={() => create.mutate()}>{create.isPending ? "Creating…" : "Create staff"}</button>}
    <button className="btn" onClick={onClose}>Close</button>
  </div></div>;
}

function ImportModal({ onClose }: { onClose: () => void }) {
  const [preview, setPreview] = useState<any | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const upload = async (file: File) => {
    setBusy(true); setMsg("");
    const fd = new FormData(); fd.append("file", file);
    try { setPreview((await api.post("/admin/staff/import/preview/", fd)).data); }
    catch (e) { setMsg(errorOf(e).message); }
    finally { setBusy(false); }
  };

  const commit = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/admin/staff/import/commit/", { token: preview.token });
      setMsg(`Imported ${data.created} staff.`);
      setTimeout(onClose, 1200);
    } catch (e) { setMsg(errorOf(e).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 900, margin: "0 auto" }}>
        <h3>Bulk import staff</h3>
        <p className="muted">
          Upload a CSV or Excel file containing staff information. The downloadable template includes an optional Phone column.
        </p>
        <a className="link" href="/staff-import-sample.csv" download>Download sample CSV template</a>
        {!preview && <input type="file" accept=".csv,.xlsx" onChange={(e) => e.target.files && upload(e.target.files[0])} />}
        {preview && (
          <>
            <p><b>{preview.valid}</b> valid · <b>{preview.invalid}</b> invalid of {preview.total} rows</p>
            <div className="table-wrap" style={{ maxHeight: 300 }}>
              <table>
                <thead><tr><th>IPPIS</th><th>Name</th><th>Email</th><th>Role(s)</th><th>Issues</th></tr></thead>
                <tbody>
                  {preview.rows.map((r: any, i: number) => (
                    <tr key={i} style={{ background: r.valid ? "" : "#fde2df" }}>
                      <td>{r.ippis_number}</td><td>{r.first_name} {r.last_name}</td><td>{r.email}</td><td>{r.role || "—"}</td>
                      <td>{r.errors.join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button className="btn primary" disabled={busy || preview.valid === 0} onClick={commit}>
              {busy ? "Importing…" : `Import ${preview.valid} valid row(s)`}
            </button>
          </>
        )}
        {msg && <div className="alert success">{msg}</div>}
        <button className="btn" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
