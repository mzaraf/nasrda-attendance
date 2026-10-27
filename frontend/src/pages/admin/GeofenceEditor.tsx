import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, TileLayer, Polygon, Marker, useMapEvents, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { api, errorOf } from "../../api";

const TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
type Pt = [number, number];
type Geofence = { id: number; name: string; kind: "circle" | "polygon"; polygon: Pt[] | null; is_active: boolean };
type Campus = { id: number; name: string; latitude: number; longitude: number; geofences: Geofence[] };
const dot = L.divIcon({ className: "vertex", iconSize: [18, 18] });

function Clicker({ onAdd }: { onAdd: (p: Pt) => void }) { useMapEvents({ click: (e) => onAdd([e.latlng.lat, e.latlng.lng]) }); return null; }
function Recentre({ centre }: { centre: Pt }) { const map = useMap(); useEffect(() => { map.setView(centre, 15); }, [centre[0], centre[1]]); return null; }

export default function GeofenceEditor() {
  const qc = useQueryClient();
  const { data: campuses = [] } = useQuery({ queryKey: ["campuses"], queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Campus[]) });
  const [campusId, setCampusId] = useState<number | "">("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [addingOffice, setAddingOffice] = useState(false);
  const [name, setName] = useState(""); const [pts, setPts] = useState<Pt[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null); const [saving, setSaving] = useState(false); const [newCampusOpen, setNewCampusOpen] = useState(false);
  const campus = campuses.find((c) => c.id === campusId);
  const selected = campus?.geofences.find((g) => g.id === selectedId);
  const centre: Pt = selected?.polygon?.[0] ?? (campus ? [campus.latitude, campus.longitude] : [9.0765, 7.3986]);
  const selectOffice = (fence: Geofence) => { setSelectedId(fence.id); setAddingOffice(false); setName(fence.name); setPts(fence.polygon ?? []); setMsg(null); };
  const addOffice = () => { setSelectedId(null); setAddingOffice(true); setName(""); setPts([]); setMsg(null); };
  useEffect(() => { setSelectedId(null); setAddingOffice(false); setName(""); setPts([]); setMsg(null); }, [campusId]);

  const save = async () => {
    if (!campusId || !name.trim()) return;
    setSaving(true); setMsg(null);
    try {
      const payload = { name: name.trim(), polygon: pts, is_active: true };
      if (selectedId) await api.patch(`/admin/geofences/${selectedId}/`, payload);
      else { const { data } = await api.post("/admin/geofences/", { campus: campusId, kind: "polygon", ...payload }); setSelectedId(data.id); setAddingOffice(false); }
      await qc.invalidateQueries({ queryKey: ["campuses"] }); setMsg({ ok: true, text: "Office geofence saved." });
    } catch (e) { setMsg({ ok: false, text: errorOf(e).message }); } finally { setSaving(false); }
  };
  const remove = async () => {
    if (!selectedId || !selected || !confirm(`Remove the ${selected.name} geofence?`)) return;
    setSaving(true); setMsg(null);
    try { await api.delete(`/admin/geofences/${selectedId}/`); setSelectedId(null); setAddingOffice(false); setName(""); setPts([]); await qc.invalidateQueries({ queryKey: ["campuses"] }); setMsg({ ok: true, text: "Office geofence removed." }); }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); } finally { setSaving(false); }
  };
  const toggle = async () => {
    if (!selected) return;
    setSaving(true); setMsg(null);
    try { await api.patch(`/admin/geofences/${selected.id}/`, { is_active: !selected.is_active }); await qc.invalidateQueries({ queryKey: ["campuses"] }); setMsg({ ok: true, text: `Office geofence ${selected.is_active ? "disabled" : "enabled"}.` }); }
    catch (e) { setMsg({ ok: false, text: errorOf(e).message }); } finally { setSaving(false); }
  };

  return <div className="gf-page">
    <div className="gf-toolbar"><div><label>Campus</label><select value={campusId} onChange={(e) => setCampusId(e.target.value ? Number(e.target.value) : "")}><option value="">Select a campus…</option>{campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div><button className={`btn ${newCampusOpen ? "primary gf-add-active" : ""}`} onClick={() => { setAddingOffice(false); setNewCampusOpen(true); }}>+ New campus</button>{campusId && <button className={`btn ${addingOffice ? "primary gf-add-active" : ""}`} onClick={addOffice}>+ Add office location</button>}</div>
    {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}
    {campus ? <><div className="gf-controls"><section className="gf-offices card"><div><h3>Office locations</h3><small>Staff assigned to this campus can attend from any active office boundary below.</small></div><div className="gf-office-list">{campus.geofences.map((fence) => <button key={fence.id} className={`gf-office ${selectedId === fence.id ? "active" : ""}`} onClick={() => selectOffice(fence)}><span>{fence.name}</span><small>{fence.kind} · {fence.is_active ? "Active" : "Disabled"}</small></button>)}{!campus.geofences.length && <small className="muted">No office locations have been added yet.</small>}</div></section>
      <section className="gf-draft card"><h3>{selected ? `Edit ${selected.name}` : "Add office location"}</h3>{selected?.kind === "circle" ? <p className="muted">This existing circle geofence cannot be edited on this map. Create a polygon office location instead.</p> : <><label>Office location name</label><input value={name} placeholder="e.g. NASRDA Annex" onChange={(e) => setName(e.target.value)} /><small className="muted">Pan or zoom the map to the office location, then click at least three points to draw its boundary.</small><div className="gf-actions"><button className="btn" disabled={!pts.length || saving} onClick={() => setPts(pts.slice(0, -1))}>Undo point</button><button className="btn" disabled={!pts.length || saving} onClick={() => setPts([])}>Clear boundary</button><button className="btn primary" disabled={pts.length < 3 || !name.trim() || saving} onClick={save}>{saving ? "Saving…" : "Save office"}</button>{selected && <span className="gf-state-actions"><button className="btn" disabled={saving} onClick={toggle}>{selected.is_active ? "Disable office" : "Enable office"}</button><button className="btn danger" disabled={saving} onClick={remove}>Remove office</button></span>}</div></>}</section></div>
      <div className="gf-map"><MapContainer center={centre} zoom={15} style={{ height: "100%", width: "100%" }}><TileLayer url={TILES} attribution="© OpenStreetMap" /><Recentre centre={centre} /><Clicker onAdd={(p) => (addingOffice || selected?.kind === "polygon") ? setPts([...pts, p]) : undefined} />{campus.geofences.filter((fence) => fence.id !== selectedId && fence.kind === "polygon" && fence.polygon && fence.polygon.length >= 3).map((fence) => <Polygon key={fence.id} positions={fence.polygon!} pathOptions={{ color: fence.is_active ? "#6b7a8c" : "#c0392b", fillOpacity: 0.12 }} />)}{pts.length >= 3 && <Polygon positions={pts} pathOptions={{ color: "#19297D" }} />}{pts.map((p, i) => <Marker key={i} position={p} icon={dot} draggable eventHandlers={{ dragend: (e) => { const ll = (e.target as L.Marker).getLatLng(); setPts(pts.map((q, j) => j === i ? [ll.lat, ll.lng] : q)); } }} />)}</MapContainer></div></> : <div className="gf-empty"><p className="muted">Select a campus above to add office locations and draw their boundaries.</p></div>}
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
