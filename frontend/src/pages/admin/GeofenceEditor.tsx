import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, TileLayer, Polygon, Marker, useMapEvents, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { api, errorOf } from "../../api";

const TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
type Pt = [number, number];
type Department = { id: number; name: string; campus_ids: number[] };
type Geofence = { id: number; name: string; kind: "circle" | "polygon"; polygon: Pt[] | null; is_active: boolean; department_ids: number[]; departments: string[] };
type Campus = { id: number; name: string; latitude: number; longitude: number; boundary: Pt[] | null; department_ids: number[]; geofences: Geofence[] };
const dot = L.divIcon({ className: "vertex", iconSize: [18, 18] });

function Clicker({ onAdd }: { onAdd: (p: Pt) => void }) { useMapEvents({ click: (e) => onAdd([e.latlng.lat, e.latlng.lng]) }); return null; }
function Recentre({ centre }: { centre: Pt }) { const map = useMap(); useEffect(() => { map.setView(centre, 15); }, [centre[0], centre[1]]); return null; }

export default function GeofenceEditor() {
  const qc = useQueryClient();
  const { data: campuses = [] } = useQuery({ queryKey: ["campuses"], queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Campus[]) });
  const { data: departments = [] } = useQuery({ queryKey: ["departments"], queryFn: () => api.get("/admin/departments/").then((r) => r.data as Department[]) });
  const [campusId, setCampusId] = useState<number | "">("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [addingOffice, setAddingOffice] = useState(false);
  const [editingCampusBoundary, setEditingCampusBoundary] = useState(false);
  const [name, setName] = useState(""); const [pts, setPts] = useState<Pt[]>([]); const [boundaryPts, setBoundaryPts] = useState<Pt[]>([]); const [departmentIds, setDepartmentIds] = useState<number[]>([]); const [departmentPickerOpen, setDepartmentPickerOpen] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null); const [saving, setSaving] = useState(false); const [newCampusOpen, setNewCampusOpen] = useState(false);
  const campus = campuses.find((c) => c.id === campusId);
  const selected = campus?.geofences.find((g) => g.id === selectedId);
  const activePts = editingCampusBoundary ? boundaryPts : pts;
  // Drawing points must not change this value: Recentre would otherwise reset
  // the map zoom after every click. Recenter only when selecting a campus/building.
  const centre: Pt = selected?.polygon?.[0] ?? campus?.boundary?.[0] ?? (campus ? [campus.latitude, campus.longitude] : [9.0765, 7.3986]);
  const campusDepartments = departments.filter((department) => campus?.department_ids.includes(department.id));
  const selectOffice = (fence: Geofence) => { setSelectedId(fence.id); setAddingOffice(false); setEditingCampusBoundary(false); setDepartmentPickerOpen(false); setName(fence.name); setPts(fence.polygon ?? []); setDepartmentIds(fence.department_ids ?? []); setMsg(null); };
  const addOffice = () => { if (!campus?.boundary) { setMsg({ ok: false, text: "Draw and save the campus boundary before adding a building." }); return; } setSelectedId(null); setAddingOffice(true); setEditingCampusBoundary(false); setDepartmentPickerOpen(false); setName(""); setPts([]); setDepartmentIds([]); setMsg(null); };
  const cancelBuildingEdit = () => { setSelectedId(null); setAddingOffice(false); setEditingCampusBoundary(false); setDepartmentPickerOpen(false); setName(""); setPts([]); setDepartmentIds([]); setMsg(null); };
  const editCampusBoundary = () => { if (!campus) return; setSelectedId(null); setAddingOffice(false); setEditingCampusBoundary(true); setBoundaryPts(campus.boundary ?? []); setMsg(null); };
  useEffect(() => { setSelectedId(null); setAddingOffice(false); setEditingCampusBoundary(false); setName(""); setPts([]); setBoundaryPts([]); setDepartmentIds([]); setMsg(null); }, [campusId]);

  const save = async () => {
    if (!campusId || !name.trim()) return;
    setSaving(true); setMsg(null);
    try {
      const payload = { name: name.trim(), polygon: pts, department_ids: departmentIds, is_active: true };
      if (selectedId) await api.patch(`/admin/geofences/${selectedId}/`, payload);
      else { const { data } = await api.post("/admin/geofences/", { campus: campusId, kind: "polygon", ...payload }); setSelectedId(data.id); setAddingOffice(false); }
      await qc.invalidateQueries({ queryKey: ["campuses"] }); setMsg({ ok: true, text: "Office geofence saved." });
    } catch (e) { setMsg({ ok: false, text: errorOf(e).message }); } finally { setSaving(false); }
  };
  const saveCampusBoundary = async () => {
    if (!campus || boundaryPts.length < 3) return;
    setSaving(true); setMsg(null);
    try { await api.patch(`/admin/campuses/${campus.id}/`, { boundary: boundaryPts }); await qc.invalidateQueries({ queryKey: ["campuses"] }); setEditingCampusBoundary(false); setMsg({ ok: true, text: "Campus boundary saved." }); }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); } finally { setSaving(false); }
  };
  const remove = async () => {
    if (!selectedId || !selected || !confirm(`Remove the ${selected.name} geofence?`)) return;
    setSaving(true); setMsg(null);
    try { await api.delete(`/admin/geofences/${selectedId}/`); setSelectedId(null); setAddingOffice(false); setName(""); setPts([]); setDepartmentIds([]); await qc.invalidateQueries({ queryKey: ["campuses"] }); setMsg({ ok: true, text: "Building removed." }); }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); } finally { setSaving(false); }
  };
  const toggle = async () => {
    if (!selected) return;
    setSaving(true); setMsg(null);
    try { await api.patch(`/admin/geofences/${selected.id}/`, { is_active: !selected.is_active }); await qc.invalidateQueries({ queryKey: ["campuses"] }); setMsg({ ok: true, text: `Building ${selected.is_active ? "disabled" : "enabled"}.` }); }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); } finally { setSaving(false); }
  };

  return <div className="gf-page">
    <div className="gf-toolbar"><div><label>Campus</label><select value={campusId} onChange={(e) => setCampusId(e.target.value ? Number(e.target.value) : "")}><option value="">Select a campus…</option>{campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div><button className={`btn ${newCampusOpen ? "primary gf-add-active" : ""}`} onClick={() => { setAddingOffice(false); setEditingCampusBoundary(false); setNewCampusOpen(true); }}>+ New campus</button>{campusId && <button className={`btn ${editingCampusBoundary ? "primary gf-add-active" : ""}`} onClick={editCampusBoundary}>Draw campus boundary</button>}{campusId && <button className={`btn ${addingOffice ? "primary gf-add-active" : ""}`} disabled={!campus?.boundary} title={!campus?.boundary ? "Draw and save the campus boundary first" : undefined} onClick={addOffice}>+ Add building</button>}</div>
    {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}
    {campus ? <><div className={`gf-controls ${departmentPickerOpen ? "gf-department-picker-open" : ""}`}><section className="gf-offices card"><div><h3>Buildings / office locations</h3><small>Each building must be inside this campus boundary and can serve one or more departments.</small></div><div className="gf-office-list">{campus.geofences.map((fence) => <button key={fence.id} className={`gf-office ${selectedId === fence.id ? "active" : ""}`} onClick={() => selectOffice(fence)}><span>{fence.name}</span><small>{fence.departments?.join(", ") || "No departments assigned"}</small></button>)}{!campus.geofences.length && <small className="muted">No buildings have been added yet.</small>}</div></section>
      <section className="gf-draft card">{editingCampusBoundary ? <><h3>Campus boundary</h3><small className="muted">Draw the outer boundary of the campus. Every building must remain inside it.</small><div className="gf-actions"><button className="btn" disabled={!boundaryPts.length || saving} onClick={() => setBoundaryPts((points) => points.slice(0, -1))}>Undo point</button><button className="btn" disabled={!boundaryPts.length || saving} onClick={() => setBoundaryPts([])}>Clear boundary</button><button className="btn primary" disabled={boundaryPts.length < 3 || saving} onClick={saveCampusBoundary}>{saving ? "Saving…" : "Save campus boundary"}</button></div></> : selected?.kind === "circle" ? <p className="muted">This legacy circle cannot be used as a department building. Create a polygon building instead.</p> : <><h3>{selected ? `Edit ${selected.name}` : "Add building"}</h3><label>Building name</label><input value={name} placeholder="e.g. Admin Block" onChange={(e) => setName(e.target.value)} /><label>Departments using this building</label><div className="gf-department-picker"><button type="button" className="gf-department-trigger" onClick={() => setDepartmentPickerOpen((open) => !open)} aria-expanded={departmentPickerOpen}>{departmentIds.length ? `${departmentIds.length} department${departmentIds.length === 1 ? "" : "s"} selected` : "Select departments"}<span>⌄</span></button>{departmentPickerOpen && <div className="gf-department-menu">{campusDepartments.length ? campusDepartments.map((department) => <label key={department.id}><input type="checkbox" checked={departmentIds.includes(department.id)} onChange={() => setDepartmentIds((ids) => ids.includes(department.id) ? ids.filter((id) => id !== department.id) : [...ids, department.id])} />{department.name}</label>) : <small className="muted">No departments are assigned to this campus</small>}</div>}</div><small className="muted">Select one or more departments, then draw at least three points on the map.</small><div className="gf-actions"><button className="btn" disabled={!pts.length || saving} onClick={() => setPts(pts.slice(0, -1))}>Undo point</button><button className="btn" disabled={!pts.length || saving} onClick={() => setPts([])}>Clear boundary</button><button className="btn primary" disabled={pts.length < 3 || !name.trim() || !departmentIds.length || saving} onClick={save}>{saving ? "Saving…" : "Save building"}</button>{selected && <button className="btn" disabled={saving} onClick={cancelBuildingEdit}>Cancel</button>}{selected && <span className="gf-state-actions"><button className="btn" disabled={saving} onClick={toggle}>{selected.is_active ? "Disable building" : "Enable building"}</button><button className="btn danger" disabled={saving} onClick={remove}>Remove building</button></span>}</div></>}</section></div>
      <div className="gf-map"><MapContainer center={centre} zoom={15} style={{ height: "100%", width: "100%" }}><TileLayer url={TILES} attribution="© OpenStreetMap" /><Recentre centre={centre} /><Clicker onAdd={(p) => { if (editingCampusBoundary) setBoundaryPts((points) => [...points, p]); else if (addingOffice || selected?.kind === "polygon") setPts((points) => [...points, p]); }} />{campus.boundary && !editingCampusBoundary && <Polygon positions={campus.boundary} pathOptions={{ color: "#17803d", fillOpacity: 0.05, weight: 3 }} />}{editingCampusBoundary && boundaryPts.length >= 3 && <Polygon positions={boundaryPts} pathOptions={{ color: "#17803d", fillOpacity: 0.12, weight: 3 }} />}{campus.geofences.filter((fence) => fence.id !== selectedId && fence.kind === "polygon" && fence.polygon && fence.polygon.length >= 3).map((fence) => <Polygon key={fence.id} positions={fence.polygon!} pathOptions={{ color: fence.is_active ? "#6b7a8c" : "#c0392b", fillOpacity: 0.12 }} />)}{!editingCampusBoundary && pts.length >= 3 && <Polygon positions={pts} pathOptions={{ color: "#19297D" }} />}{activePts.map((p, i) => <Marker key={i} position={p} icon={dot} draggable eventHandlers={{ dragend: (e) => { const ll = (e.target as L.Marker).getLatLng(); if (editingCampusBoundary) setBoundaryPts((points) => points.map((q, j) => j === i ? [ll.lat, ll.lng] : q)); else setPts((points) => points.map((q, j) => j === i ? [ll.lat, ll.lng] : q)); } }} />)}</MapContainer></div></> : <div className="gf-empty"><p className="muted">Select a campus to draw its boundary and manage its buildings.</p></div>}
    {newCampusOpen && <NewCampusModal onClose={() => setNewCampusOpen(false)} onCreated={(id) => { setCampusId(id); setNewCampusOpen(false); qc.invalidateQueries({ queryKey: ["campuses"] }); }} />}
  </div>;
}

function NewCampusModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const [form, setForm] = useState({ name: "", latitude: "", longitude: "" });
  const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true); setMsg("");
    try {
      const { data } = await api.post("/admin/campuses/", { name: form.name.trim(), latitude: Number(form.latitude), longitude: Number(form.longitude), is_active: true });
      onCreated(data.id);
    } catch (e) { setMsg(errorOf(e).message); } finally { setBusy(false); }
  };
  return <div className="sheet-backdrop" onClick={onClose}><div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480, margin: "0 auto" }}><h3>New campus</h3><label>Campus name</label><input value={form.name} placeholder="e.g. NASRDA Headquarters" onChange={(e) => setForm({ ...form, name: e.target.value })} /><div className="row"><div><label>Latitude</label><input value={form.latitude} placeholder="e.g. 9.0579" inputMode="decimal" onChange={(e) => setForm({ ...form, latitude: e.target.value })} /></div><div><label>Longitude</label><input value={form.longitude} placeholder="e.g. 7.4951" inputMode="decimal" onChange={(e) => setForm({ ...form, longitude: e.target.value })} /></div></div><p className="muted" style={{ fontSize: 12 }}>Use the campus’s approximate centre. You can add separate office boundaries afterwards.</p>{msg && <div className="alert error">{msg}</div>}<button className="btn primary" disabled={busy || !form.name.trim() || !form.latitude || !form.longitude} onClick={create}>{busy ? "Creating…" : "Create campus"}</button><button className="btn" onClick={onClose}>Cancel</button></div></div>;
}
