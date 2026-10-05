import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, TileLayer, Polygon, Marker, useMapEvents, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { api, errorOf } from "../../api";

const TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
type Pt = [number, number];
type Campus = { id: number; name: string; latitude: number; longitude: number;
                department_ids: number[]; departments: string[]; geofences: { id: number; kind: string; polygon: Pt[] | null }[] };
const dot = L.divIcon({ className: "vertex", iconSize: [18, 18] });

function Clicker({ onAdd }: { onAdd: (p: Pt) => void }) {
  useMapEvents({ click: (e) => onAdd([e.latlng.lat, e.latlng.lng]) });
  return null;
}
function Recentre({ centre }: { centre: Pt }) {
  const map = useMap();
  useEffect(() => { map.setView(centre, 17); }, [centre[0], centre[1]]);
  return null;
}

export default function GeofenceEditor() {
  const qc = useQueryClient();
  const { data: campuses = [] } = useQuery({
    queryKey: ["campuses"],
    queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Campus[]),
  });
  const [campusId, setCampusId] = useState<number | "">("");
  const [pts, setPts] = useState<Pt[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [newCampusOpen, setNewCampusOpen] = useState(false);

  const campus = campuses.find((c) => c.id === campusId);
  const centre: Pt = campus ? [campus.latitude, campus.longitude] : [9.0765, 7.3986];
  const existingGeofenceId = campus?.geofences.find((g) => g.kind === "polygon")?.id;

  // Load that campus's existing boundary when you switch campuses.
  useEffect(() => {
    const poly = campus?.geofences.find((g) => g.kind === "polygon")?.polygon;
    setPts(poly ?? []);
    setMsg(null);
  }, [campusId]);

  const save = async () => {
    if (!campusId) return;
    setSaving(true); setMsg(null);
    try {
      if (existingGeofenceId) {
        await api.patch(`/admin/geofences/${existingGeofenceId}/`, { polygon: pts, is_active: true });
      } else {
        await api.post("/admin/geofences/", { campus: campusId, kind: "polygon", polygon: pts, is_active: true });
      }
      await qc.invalidateQueries({ queryKey: ["campuses"] });
      setMsg({ ok: true, text: "Geofence saved." });
    } catch (e) {
      setMsg({ ok: false, text: errorOf(e).message });
    } finally { setSaving(false); }
  };

  return (
    <div className="gf-page">
      <div className="gf-toolbar">
        <div>
          <label>Campus</label>
          <select value={campusId} onChange={(e) => setCampusId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Select a campus…</option>
            {campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <button className="btn" onClick={() => setNewCampusOpen(true)}>+ New campus</button>
        <div className="gf-spacer" />
        {campusId && (
          <>
            <button className="btn" disabled={!pts.length} onClick={() => setPts(pts.slice(0, -1))}>Undo</button>
            <button className="btn" disabled={!pts.length} onClick={() => setPts([])}>Clear</button>
            <button className="btn primary" disabled={pts.length < 3 || saving} onClick={save}>
              {saving ? (<><span className="spinner" /> Saving…</>) : "Save boundary"}
            </button>
          </>
        )}
      </div>

      {msg && <div className={`alert ${msg.ok ? "success" : "error"}`}>{msg.text}</div>}

      {campusId ? (
        <div className="gf-map">
          <MapContainer center={centre} zoom={17} style={{ height: "100%", width: "100%" }}>
            <TileLayer url={TILES} attribution="© OpenStreetMap" />
            <Recentre centre={centre} />
            <Clicker onAdd={(p) => setPts([...pts, p])} />
            {pts.length >= 3 && <Polygon positions={pts} />}
            {pts.map((p, i) => (
              <Marker key={i} position={p} icon={dot} draggable
                eventHandlers={{ dragend: (e) => {
                  const ll = (e.target as L.Marker).getLatLng();
                  setPts(pts.map((q, j) => (j === i ? [ll.lat, ll.lng] : q)));
                } }} />
            ))}
          </MapContainer>
        </div>
      ) : (
        <div className="gf-empty"><p className="muted">Select a campus above to view or draw its boundary.</p></div>
      )}

      {newCampusOpen && (
        <NewCampusModal
          onClose={() => setNewCampusOpen(false)}
          onCreated={(id) => { setCampusId(id); setNewCampusOpen(false); qc.invalidateQueries({ queryKey: ["campuses"] }); }}
        />
      )}
    </div>
  );
}

function NewCampusModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const [form, setForm] = useState({ name: "", latitude: "", longitude: "" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true); setMsg("");
    try {
      const { data } = await api.post("/admin/campuses/", {
        name: form.name, latitude: Number(form.latitude), longitude: Number(form.longitude), is_active: true,
      });
      onCreated(data.id);
    } catch (e) { setMsg(errorOf(e).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480, margin: "0 auto" }}>
        <h3>New campus</h3>
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <div className="row">
          <div><label>Latitude</label>
            <input value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} /></div>
          <div><label>Longitude</label>
            <input value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} /></div>
        </div>
        <p className="muted" style={{ fontSize: 12 }}>
          Use the campus's approximate centre — you'll draw the exact boundary on the map next.
        </p>
        {msg && <div className="alert error">{msg}</div>}
        <button className="btn primary" disabled={busy || !form.name || !form.latitude || !form.longitude} onClick={create}>
          {busy ? (<><span className="spinner" /> Creating…</>) : "Create campus"}
        </button>
        <button className="btn" onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}
