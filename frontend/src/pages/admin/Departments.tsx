import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../../api";

type Campus = { id: number; name: string };
type Department = { id: number; name: string; campus_ids: number[] };

export default function Departments() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Department | null>(null);
  const { data: departments = [] } = useQuery({ queryKey: ["departments"], queryFn: () => api.get("/admin/departments/").then((r) => r.data as Department[]) });
  const remove = useMutation({ mutationFn: (id: number) => api.delete(`/admin/departments/${id}/`), onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }) });
  return <div className="page wide"><div className="row"><h2 style={{ marginRight: "auto" }}>Departments</h2><button className="btn primary" onClick={() => setEditing({ id: 0, name: "", campus_ids: [] })}>+ New department</button></div><div className="departments-table-gap" /><div className="table-wrap"><table><thead><tr><th>Department</th><th>Campus(es)</th><th></th></tr></thead><tbody>{departments.map((department) => <tr key={department.id}><td><b>{department.name}</b></td><td>{department.campus_ids.length ? department.campus_ids.length + " assigned" : "Not assigned"}</td><td className="row"><button className="link" onClick={() => setEditing(department)}>Edit</button><button className="link" disabled={remove.isPending} onClick={() => remove.mutate(department.id)}>Delete</button></td></tr>)}</tbody></table></div>{editing && <DepartmentModal department={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["departments"] }); }} />}</div>;
}

function DepartmentModal({ department, onClose, onSaved }: { department: Department; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(department.name);
  const [campusIds, setCampusIds] = useState(department.campus_ids);
  const [message, setMessage] = useState("");
  const { data: campuses = [] } = useQuery({ queryKey: ["campuses"], queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Campus[]) });
  const save = useMutation({ mutationFn: () => department.id ? api.patch(`/admin/departments/${department.id}/`, { name, campus_ids: campusIds }) : api.post("/admin/departments/", { name, campus_ids: campusIds }), onSuccess: onSaved, onError: (e) => setMessage(errorOf(e).message) });
  return <div className="sheet-backdrop" onClick={onClose}><div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560, margin: "0 auto" }}><h3>{department.id ? "Edit department" : "New department"}</h3><label>Department name</label><input value={name} onChange={(e) => setName(e.target.value)} /><label>Campus assignment</label><select multiple value={campusIds.map(String)} onChange={(e) => setCampusIds(Array.from(e.target.selectedOptions, (option) => Number(option.value)))}>{campuses.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}</select><small className="muted">Hold Ctrl (or Cmd) to assign this department to multiple campuses.</small>{message && <div className="alert error">{message}</div>}<button className="btn primary" disabled={!name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save department"}</button><button className="btn" onClick={onClose}>Cancel</button></div></div>;
}
