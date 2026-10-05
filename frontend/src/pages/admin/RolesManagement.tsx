import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../../api";

type Permission = { id: number; name: string; code: string };
type Role = { id: number; name: string; permission_ids: number[]; permissions: Permission[]; member_count: number };

export default function RolesManagement() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Role | null>(null);
  const { data: roles = [] } = useQuery({ queryKey: ["roles"], queryFn: () => api.get("/admin/roles/").then((r) => r.data as Role[]) });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/admin/roles/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["roles"] }),
  });

  return <div className="page wide">
    <div className="row"><h2 style={{ marginRight: "auto" }}>Roles & permissions</h2><button className="btn primary" onClick={() => setEditing({ id: 0, name: "", permission_ids: [], permissions: [], member_count: 0 })}>+ New role</button></div>
    <div className="roles-table-gap" />
    <div className="table-wrap"><table><thead><tr><th>Role</th><th>Permissions</th><th>Assigned staff</th><th></th></tr></thead><tbody>
      {roles.map((role) => <tr key={role.id}><td><b>{role.name}</b></td><td>{role.permissions.map((p) => p.name).join(", ") || "No permissions"}</td><td>{role.member_count}</td><td className="row"><button className="link" onClick={() => setEditing(role)}>Edit</button><button className="link" disabled={role.member_count > 0 || remove.isPending} onClick={() => remove.mutate(role.id)}>Delete</button></td></tr>)}
    </tbody></table></div>
    {editing && <RoleModal role={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["roles"] }); }} />}
  </div>;
}

function RoleModal({ role, onClose, onSaved }: { role: Role; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(role.name);
  const [selected, setSelected] = useState<number[]>(role.permissions.map((p) => p.id));
  const [msg, setMsg] = useState("");
  const save = useMutation({
    mutationFn: () => role.id ? api.patch(`/admin/roles/${role.id}/`, { name, permission_ids: selected }) : api.post("/admin/roles/", { name, permission_ids: selected }),
    onSuccess: onSaved,
    onError: (e) => setMsg(errorOf(e).message),
  });
  const { data: permissions = [] } = useQuery({ queryKey: ["permissions"], queryFn: () => api.get("/admin/permissions/").then((r) => r.data as Permission[]) });
  const toggle = (id: number) => setSelected((current) => current.includes(id) ? current.filter((p) => p !== id) : [...current, id]);

  return <div className="sheet-backdrop" onClick={onClose}><div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 680, margin: "0 auto" }}>
    <h3>{role.id ? "Edit role" : "Create role"}</h3>
    <label>Role name</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. HR Officer" />
    <label>Permissions</label>
    <div className="card" style={{ maxHeight: 360, overflowY: "auto" }}>{permissions.map((p) => <label key={p.id} className="row" style={{ margin: "8px 0" }}><input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} /> <span><b>{p.name}</b><small>{p.code}</small></span></label>)}</div>
    {msg && <div className="alert error">{msg}</div>}
    <button className="btn primary" disabled={!name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save role"}</button><button className="btn" onClick={onClose}>Cancel</button>
  </div></div>;
}
