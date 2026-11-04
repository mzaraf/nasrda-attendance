import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../../api";
import { useAuth } from "../../auth";

type Campus = { id: number; name: string };
type Department = { id: number; name: string; campus_ids: number[] };

export default function Departments() {
  const { me } = useAuth();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Department | null>(null);
  const [selectedCampus, setSelectedCampus] = useState("");
  const { data: departments = [] } = useQuery({ queryKey: ["departments"], queryFn: () => api.get("/admin/departments/").then((r) => r.data as Department[]) });
  const { data: campuses = [] } = useQuery({ queryKey: ["campuses"], queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Campus[]) });
  const remove = useMutation({ mutationFn: (id: number) => api.delete(`/admin/departments/${id}/`), onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }) });
  useEffect(() => {
    if (!selectedCampus && me?.primary_campus_id && campuses.some((item) => item.id === me.primary_campus_id)) {
      setSelectedCampus(String(me.primary_campus_id));
    }
  }, [campuses, me?.primary_campus_id, selectedCampus]);
  const campus = campuses.find((item) => String(item.id) === selectedCampus);
  const visibleDepartments = campus ? departments.filter((department) => department.campus_ids.includes(campus.id)) : [];
  const startNewDepartment = () => setEditing({
    id: 0,
    name: "",
    // The campus currently being viewed is the natural home for a new
    // department. It is still editable in the form when needed.
    campus_ids: campus ? [campus.id] : [],
  });

  const confirmDelete = (department: Department) => {
    if (window.confirm(`Delete ${department.name} department? This cannot be undone.`)) remove.mutate(department.id);
  };
  const table = (items: Department[]) => <div className="table-wrap"><table><thead><tr><th>Department</th><th></th></tr></thead><tbody>{items.map((department) => <tr key={department.id}><td><b>{department.name}</b></td><td className="row"><button className="link" onClick={() => setEditing(department)}>Edit</button><button className="link" disabled={remove.isPending} onClick={() => confirmDelete(department)}>Delete</button></td></tr>)}</tbody></table></div>;

  return <div className="page wide"><div className="department-page-actions"><div className="department-page-title"><h2>Departments</h2><p>View and manage departments by campus.</p></div><div className="department-page-controls"><div className="department-campus-picker"><label htmlFor="department-campus">Campus</label><select id="department-campus" value={selectedCampus} onChange={(event) => setSelectedCampus(event.target.value)}><option value="">Select a campus…</option>{campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><button className="btn primary" onClick={startNewDepartment}>+ New department</button></div></div><div className="departments-table-gap" />
    {selectedCampus && <section className="department-campus-group"><div className="department-campus-heading"><h3>{campus?.name}</h3><span>{visibleDepartments.length} {visibleDepartments.length === 1 ? "department" : "departments"}</span></div>{visibleDepartments.length ? table(visibleDepartments) : <div className="empty-state">No departments are assigned to this campus yet.</div>}</section>}
    {!departments.length && <div className="empty-state">No departments have been created yet.</div>}
    {editing && <DepartmentModal department={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["departments"] }); }} />}</div>;
}

function DepartmentModal({ department, onClose, onSaved }: { department: Department; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(department.name);
  const [campusIds, setCampusIds] = useState(department.campus_ids);
  const [message, setMessage] = useState("");
  const { data: campuses = [] } = useQuery({ queryKey: ["campuses"], queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Campus[]) });
  const save = useMutation({ mutationFn: () => department.id ? api.patch(`/admin/departments/${department.id}/`, { name, campus_ids: campusIds }) : api.post("/admin/departments/", { name, campus_ids: campusIds }), onSuccess: onSaved, onError: (e) => setMessage(errorOf(e).message) });
  return <div className="sheet-backdrop" onClick={onClose}><div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560, margin: "0 auto" }}><h3>{department.id ? "Edit department" : "New department"}</h3><label>Department name</label><input value={name} onChange={(e) => setName(e.target.value)} /><label>Campus assignment</label><select multiple value={campusIds.map(String)} onChange={(e) => setCampusIds(Array.from(e.target.selectedOptions, (option) => Number(option.value)))}>{campuses.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}</select><small className="muted">Select at least one campus. Hold Ctrl (or Cmd) to assign this department to multiple campuses.</small>{message && <div className="alert error">{message}</div>}<button className="btn primary" disabled={!name.trim() || !campusIds.length || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save department"}</button><button className="btn" onClick={onClose}>Cancel</button></div></div>;
}
