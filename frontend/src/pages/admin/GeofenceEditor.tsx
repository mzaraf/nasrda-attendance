import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MapContainer,
  TileLayer,
  Polygon,
  Marker,
  useMap,
  useMapEvents,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { api, errorOf } from "../../api";

const TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
type Pt = [number, number];
type Department = { id: number; name: string; campus_ids: number[] };
type CampusArea = {
  id: number;
  campus: number;
  name: string;
  boundary: Pt[];
  is_active: boolean;
};
type Geofence = {
  id: number;
  campus: number;
  campus_area: number | null;
  campus_area_name: string;
  name: string;
  kind: "circle" | "polygon";
  polygon: Pt[] | null;
  is_active: boolean;
  department_ids: number[];
  departments: string[];
};
type Campus = {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  department_ids: number[];
  areas: CampusArea[];
  geofences: Geofence[];
};
const dot = L.divIcon({ className: "vertex", iconSize: [18, 18] });

function Clicker({ onAdd }: { onAdd: (point: Pt) => void }) {
  useMapEvents({
    click: (event) => onAdd([event.latlng.lat, event.latlng.lng]),
  });
  return null;
}
function Recentre({ centre, paused }: { centre: Pt; paused: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (paused) return;
    map.setView(centre, 15);
  }, [centre[0], centre[1], paused]);
  return null;
}

function FocusBuilding({ building }: { building: Geofence | undefined }) {
  const map = useMap();
  useEffect(() => {
    if (!building?.polygon || building.polygon.length < 3) return;
    const bounds = L.latLngBounds(building.polygon);
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 19 });
  }, [building?.id]);
  return null;
}

export default function GeofenceEditor() {
  const qc = useQueryClient();
  const { data: campuses = [] } = useQuery({
    queryKey: ["campuses"],
    queryFn: () => api.get("/admin/campuses/").then((r) => r.data as Campus[]),
  });
  const { data: departments = [] } = useQuery({
    queryKey: ["departments"],
    queryFn: () =>
      api.get("/admin/departments/").then((r) => r.data as Department[]),
  });
  const [campusId, setCampusId] = useState<number | "">("");
  const [mode, setMode] = useState<"idle" | "area" | "building">("idle");
  const [selectedAreaId, setSelectedAreaId] = useState<number | null>(null);
  const [selectedBuildingId, setSelectedBuildingId] = useState<number | null>(
    null,
  );
  const [name, setName] = useState("");
  const [points, setPoints] = useState<Pt[]>([]);
  const [buildingAreaId, setBuildingAreaId] = useState<number | "">("");
  const [departmentIds, setDepartmentIds] = useState<number[]>([]);
  const [departmentPickerOpen, setDepartmentPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [newCampusOpen, setNewCampusOpen] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const campus = campuses.find((item) => item.id === campusId);
  const selectedArea = campus?.areas.find((item) => item.id === selectedAreaId);
  const selectedBuilding = campus?.geofences.find(
    (item) => item.id === selectedBuildingId,
  );
  const campusDepartments = departments.filter((department) =>
    campus?.department_ids.includes(department.id),
  );
  const centre: Pt =
    points[0] ??
    selectedBuilding?.polygon?.[0] ??
    selectedArea?.boundary?.[0] ??
    campus?.areas[0]?.boundary?.[0] ??
    (campus ? [campus.latitude, campus.longitude] : [9.0765, 7.3986]);
  const reset = () => {
    setMode("idle");
    setSelectedAreaId(null);
    setSelectedBuildingId(null);
    setName("");
    setPoints([]);
    setBuildingAreaId("");
    setDepartmentIds([]);
    setDepartmentPickerOpen(false);
    setMsg(null);
  };
  useEffect(() => {
    reset();
  }, [campusId]);
  useEffect(() => {
    if (!departmentPickerOpen) return;
    const close = (event: PointerEvent) => {
      const picker = document.querySelector(".gf-department-picker");
      if (picker && !picker.contains(event.target as Node))
        setDepartmentPickerOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [departmentPickerOpen]);
  const selectArea = (area: CampusArea) => {
    setMode("area");
    setSelectedAreaId(area.id);
    setSelectedBuildingId(null);
    setName(area.name);
    setPoints(area.boundary);
    setDepartmentPickerOpen(false);
    setMsg(null);
  };
  const newArea = () => {
    setMode("area");
    setSelectedAreaId(null);
    setSelectedBuildingId(null);
    setName("");
    setPoints([]);
    setDepartmentPickerOpen(false);
    setMsg(null);
  };
  const selectBuilding = (building: Geofence) => {
    setMode("building");
    setSelectedBuildingId(building.id);
    setSelectedAreaId(null);
    setName(building.name);
    setPoints(building.polygon ?? []);
    setBuildingAreaId(building.campus_area ?? "");
    setDepartmentIds(building.department_ids);
    setDepartmentPickerOpen(false);
    setMsg(null);
  };
  const newBuilding = () => {
    if (!campus?.areas.length) {
      setMsg({
        ok: false,
        text: "Add and save a campus area before adding a building.",
      });
      return;
    }
    setMode("building");
    setSelectedBuildingId(null);
    setSelectedAreaId(null);
    setName("");
    setPoints([]);
    setBuildingAreaId(campus.areas[0].id);
    setDepartmentIds([]);
    setDepartmentPickerOpen(false);
    setMsg(null);
  };
  const saveArea = async () => {
    if (!campus || !name.trim() || points.length < 3) return;
    setSaving(true);
    setMsg(null);
    try {
      const payload = {
        campus: campus.id,
        name: name.trim(),
        boundary: points,
        is_active: true,
      };
      const response = selectedAreaId
        ? await api.patch(`/admin/campus-areas/${selectedAreaId}/`, payload)
        : await api.post("/admin/campus-areas/", payload);
      setSelectedAreaId(response.data.id);
      await qc.invalidateQueries({ queryKey: ["campuses"] });
      setMsg({ ok: true, text: "Campus area saved." });
    } catch (error) {
      setMsg({ ok: false, text: errorOf(error).message });
    } finally {
      setSaving(false);
    }
  };
  const saveBuilding = async () => {
    if (
      !campus ||
      !name.trim() ||
      !buildingAreaId ||
      points.length < 3 ||
      !departmentIds.length
    )
      return;
    setSaving(true);
    setMsg(null);
    try {
      const payload = {
        name: name.trim(),
        polygon: points,
        campus_area: buildingAreaId,
        department_ids: departmentIds,
        is_active: true,
      };
      if (selectedBuildingId)
        await api.patch(`/admin/geofences/${selectedBuildingId}/`, payload);
      else
        await api.post("/admin/geofences/", {
          campus: campus.id,
          kind: "polygon",
          ...payload,
        });
      await qc.invalidateQueries({ queryKey: ["campuses"] });
      setMsg({ ok: true, text: "Building saved." });
    } catch (error) {
      setMsg({ ok: false, text: errorOf(error).message });
    } finally {
      setSaving(false);
    }
  };
  const toggleArea = async () => {
    if (!selectedArea) return;
    setSaving(true);
    try {
      await api.patch(`/admin/campus-areas/${selectedArea.id}/`, {
        is_active: !selectedArea.is_active,
      });
      await qc.invalidateQueries({ queryKey: ["campuses"] });
      setMsg({
        ok: true,
        text: `Campus area ${selectedArea.is_active ? "disabled" : "enabled"}.`,
      });
    } catch (error) {
      setMsg({ ok: false, text: errorOf(error).message });
    } finally {
      setSaving(false);
    }
  };
  const removeArea = async () => {
    if (
      !selectedArea ||
      !confirm(`Remove ${selectedArea.name}? Remove its buildings first.`)
    )
      return;
    setSaving(true);
    try {
      await api.delete(`/admin/campus-areas/${selectedArea.id}/`);
      await qc.invalidateQueries({ queryKey: ["campuses"] });
      reset();
      setMsg({ ok: true, text: "Campus area removed." });
    } catch (error) {
      setMsg({ ok: false, text: errorOf(error).message });
    } finally {
      setSaving(false);
    }
  };
  const toggleBuilding = async () => {
    if (!selectedBuilding) return;
    setSaving(true);
    try {
      await api.patch(`/admin/geofences/${selectedBuilding.id}/`, {
        is_active: !selectedBuilding.is_active,
      });
      await qc.invalidateQueries({ queryKey: ["campuses"] });
      setMsg({
        ok: true,
        text: `Building ${selectedBuilding.is_active ? "disabled" : "enabled"}.`,
      });
    } catch (error) {
      setMsg({ ok: false, text: errorOf(error).message });
    } finally {
      setSaving(false);
    }
  };
  const removeBuilding = async () => {
    if (!selectedBuilding || !confirm(`Remove ${selectedBuilding.name}?`))
      return;
    setSaving(true);
    try {
      await api.delete(`/admin/geofences/${selectedBuilding.id}/`);
      await qc.invalidateQueries({ queryKey: ["campuses"] });
      reset();
      setMsg({ ok: true, text: "Building removed." });
    } catch (error) {
      setMsg({ ok: false, text: errorOf(error).message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="gf-page">
      <div className="gf-toolbar">
        <div>
          <label>Campus</label>
          <select
            value={campusId}
            onChange={(event) =>
              setCampusId(event.target.value ? Number(event.target.value) : "")
            }
          >
            <option value="">Select a campus…</option>
            {campuses.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <button
          className={`btn ${newCampusOpen ? "primary gf-add-active" : ""}`}
          onClick={() => setNewCampusOpen(true)}
        >
          + New campus
        </button>
        {campus && (
          <>
            <button className="btn" onClick={newArea}>
              + Add campus area
            </button>
            <button className="btn" onClick={newBuilding}>
              + Add building
            </button>
          </>
        )}
      </div>
      {msg && (
        <div className={`alert ${msg.ok ? "success" : "error"}`}>
          {msg.text}
        </div>
      )}
      {campus ? (
        <>
          <div className="gf-controls">
            <section className="gf-offices card">
              <div>
                <h3>Campus areas</h3>
              </div>
              <div className="gf-office-list">
                {campus.areas.map((area) => (
                  <button
                    key={area.id}
                    className={`gf-office ${selectedAreaId === area.id ? "active" : ""}`}
                    onClick={() => selectArea(area)}
                  >
                    <span>{area.name}</span>
                    <small>{area.is_active ? "Active" : "Disabled"}</small>
                  </button>
                ))}
                {!campus.areas.length && (
                  <small className="muted">
                    No campus areas have been added yet.
                  </small>
                )}
              </div>
              <div>
                <h3>Buildings</h3>
              </div>
              <div className="gf-office-list">
                {campus.geofences
                  .filter((building) => building.kind === "polygon")
                  .map((building) => (
                    <button
                      key={building.id}
                      className={`gf-office ${selectedBuildingId === building.id ? "active" : ""}`}
                      onClick={() => selectBuilding(building)}
                    >
                      <span>{building.name}</span>
                      <small>
                        {building.campus_area_name || "Unassigned area"} ·{" "}
                        {building.departments.join(", ") ||
                          "No departments assigned"}
                      </small>
                    </button>
                  ))}
                {!campus.geofences.length && (
                  <small className="muted">
                    No buildings have been added yet.
                  </small>
                )}
              </div>
            </section>
            <section className="gf-draft card">
              {mode === "area" ? (
                <>
                  <h3>
                    {selectedArea
                      ? `Edit ${selectedArea.name}`
                      : "Add campus area"}
                  </h3>
                  <label>Campus area name</label>
                  <input
                    value={name}
                    placeholder="e.g. NASRDA Annex"
                    onChange={(event) => setName(event.target.value)}
                  />
                  <small className="muted">
                    Draw the outer boundary of this physical campus location.
                  </small>
                  <div className="gf-actions">
                    <button
                      className="btn"
                      disabled={!points.length || saving}
                      onClick={() => setPoints((value) => value.slice(0, -1))}
                    >
                      Undo point
                    </button>
                    <button
                      className="btn"
                      disabled={!points.length || saving}
                      onClick={() => setPoints([])}
                    >
                      Clear boundary
                    </button>
                    <button className="btn" disabled={saving} onClick={reset}>
                      Cancel
                    </button>
                    <button
                      className="btn primary"
                      disabled={points.length < 3 || !name.trim() || saving}
                      onClick={saveArea}
                    >
                      {saving ? "Saving…" : "Save"}
                    </button>
                    {selectedArea && (
                      <span className="gf-state-actions">
                        <button
                          className="btn"
                          disabled={saving}
                          onClick={toggleArea}
                        >
                          {selectedArea.is_active
                            ? "Disable"
                            : "Enable"}
                        </button>
                        <button
                          className="btn danger"
                          disabled={saving}
                          onClick={removeArea}
                        >
                          Remove
                        </button>
                      </span>
                    )}
                  </div>
                </>
              ) : mode === "building" ? (
                <>
                  <h3>
                    {selectedBuilding
                      ? `Edit ${selectedBuilding.name}`
                      : "Add building"}
                  </h3>
                  <label>Building name</label>
                  <input
                    value={name}
                    placeholder="e.g. Admin Block"
                    onChange={(event) => setName(event.target.value)}
                  />
                  <label>Campus area</label>
                  <select
                    value={buildingAreaId}
                    onChange={(event) =>
                      setBuildingAreaId(
                        event.target.value ? Number(event.target.value) : "",
                      )
                    }
                  >
                    <option value="">Select campus area…</option>
                    {campus.areas.map((area) => (
                      <option key={area.id} value={area.id}>
                        {area.name}
                      </option>
                    ))}
                  </select>
                  <label>Departments using this building</label>
                  <div className="gf-department-picker">
                    <button
                      type="button"
                      className="gf-department-trigger"
                      onClick={() => setDepartmentPickerOpen((open) => !open)}
                      aria-expanded={departmentPickerOpen}
                    >
                      {departmentIds.length
                        ? `${departmentIds.length} department${departmentIds.length === 1 ? "" : "s"} selected`
                        : "Select departments"}
                      <span>⌄</span>
                    </button>
                    {departmentPickerOpen && (
                      <div className="gf-department-menu">
                        {campusDepartments.length ? (
                          campusDepartments.map((department) => (
                            <label key={department.id}>
                              <input
                                type="checkbox"
                                checked={departmentIds.includes(department.id)}
                                onChange={() =>
                                  setDepartmentIds((ids) =>
                                    ids.includes(department.id)
                                      ? ids.filter((id) => id !== department.id)
                                      : [...ids, department.id],
                                  )
                                }
                              />
                              {department.name}
                            </label>
                          ))
                        ) : (
                          <small className="muted">
                            No departments are assigned to this campus
                          </small>
                        )}
                      </div>
                    )}
                  </div>
                  <small className="muted">
                    Select departments, choose an area, then draw at least three
                    points on the map.
                  </small>
                  <div className="gf-actions">
                    <button
                      className="btn"
                      disabled={!points.length || saving}
                      onClick={() => setPoints((value) => value.slice(0, -1))}
                    >
                      Undo point
                    </button>
                    <button
                      className="btn"
                      disabled={!points.length || saving}
                      onClick={() => setPoints([])}
                    >
                      Clear boundary
                    </button>
                    <button className="btn" disabled={saving} onClick={reset}>
                      Cancel
                    </button>
                    <button
                      className="btn primary"
                      disabled={
                        points.length < 3 ||
                        !name.trim() ||
                        !buildingAreaId ||
                        !departmentIds.length ||
                        saving
                      }
                      onClick={saveBuilding}
                    >
                      {saving ? "Saving…" : "Save"}
                    </button>
                    {selectedBuilding && (
                      <span className="gf-state-actions">
                        <button
                          className="btn"
                          disabled={saving}
                          onClick={toggleBuilding}
                        >
                          {selectedBuilding.is_active
                            ? "Disable"
                            : "Enable"}
                        </button>
                        <button
                          className="btn danger"
                          disabled={saving}
                          onClick={removeBuilding}
                        >
                          Remove
                        </button>
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <h3>Campus geofencing</h3>
                  <p className="muted">
                    Add a campus area for each separate physical location, then
                    add department buildings inside that area.
                  </p>
                </>
              )}
            </section>
          </div>
          <div className="gf-map">
            <MapContainer
              center={centre}
              zoom={15}
              style={{ height: "100%", width: "100%" }}
            >
              <TileLayer url={TILES} attribution="© OpenStreetMap" />
              <Recentre centre={centre} paused={!!selectedBuilding} />
              <FocusBuilding building={selectedBuilding} />
              <Clicker
                onAdd={(point) => {
                  if (mode !== "idle") setPoints((value) => [...value, point]);
                }}
              />
              {campus.areas
                .filter((area) => area.id !== selectedAreaId)
                .map((area) => (
                  <Polygon
                    key={area.id}
                    positions={area.boundary}
                    pathOptions={{
                      color: area.is_active ? "#17803d" : "#c0392b",
                      fillOpacity: 0.05,
                      weight: 3,
                    }}
                  />
                ))}
              {mode === "area" && points.length >= 3 && (
                <Polygon
                  positions={points}
                  pathOptions={{
                    color: "#17803d",
                    fillOpacity: 0.12,
                    weight: 3,
                  }}
                />
              )}
              {campus.geofences
                .filter(
                  (building) =>
                    building.id !== selectedBuildingId &&
                    building.kind === "polygon" &&
                    building.polygon &&
                    building.polygon.length >= 3,
                )
                .map((building) => (
                  <Polygon
                    key={building.id}
                    positions={building.polygon!}
                    pathOptions={{
                      color: building.is_active ? "#6b7a8c" : "#c0392b",
                      fillOpacity: 0.12,
                    }}
                  />
                ))}
              {mode === "building" && points.length >= 3 && (
                <Polygon
                  positions={points}
                  pathOptions={{ color: "#19297D" }}
                />
              )}
              {mode !== "idle" &&
                points.map((point, index) => (
                  <Marker
                    key={index}
                    position={point}
                    icon={dot}
                    draggable
                    eventHandlers={{
                      dragend: (event) => {
                        const location = (event.target as L.Marker).getLatLng();
                        setPoints((value) =>
                          value.map((item, itemIndex) =>
                            itemIndex === index
                              ? [location.lat, location.lng]
                              : item,
                          ),
                        );
                      },
                    }}
                  />
                ))}
            </MapContainer>
          </div>
        </>
      ) : (
        <div className="gf-empty">
          <p className="muted">
            Select a campus to manage its areas and buildings.
          </p>
        </div>
      )}
      {newCampusOpen && (
        <NewCampusModal
          onClose={() => setNewCampusOpen(false)}
          onCreated={(id) => {
            setCampusId(id);
            setNewCampusOpen(false);
            qc.invalidateQueries({ queryKey: ["campuses"] });
          }}
        />
      )}
    </div>
  );
}

function NewCampusModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: number) => void;
}) {
  const [form, setForm] = useState({ name: "", latitude: "", longitude: "" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    setMsg("");
    try {
      const { data } = await api.post("/admin/campuses/", {
        name: form.name.trim(),
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        is_active: true,
      });
      onCreated(data.id);
    } catch (error) {
      setMsg(errorOf(error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div
        className="sheet"
        onClick={(event) => event.stopPropagation()}
        style={{ maxWidth: 480, margin: "0 auto" }}
      >
        <h3>New campus</h3>
        <label>Campus name</label>
        <input
          value={form.name}
          placeholder="e.g. NCRS Jos"
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
        <div className="row">
          <div>
            <label>Latitude</label>
            <input
              value={form.latitude}
              placeholder="e.g. 9.0579"
              inputMode="decimal"
              onChange={(event) =>
                setForm({ ...form, latitude: event.target.value })
              }
            />
          </div>
          <div>
            <label>Longitude</label>
            <input
              value={form.longitude}
              placeholder="e.g. 7.4951"
              inputMode="decimal"
              onChange={(event) =>
                setForm({ ...form, longitude: event.target.value })
              }
            />
          </div>
        </div>
        <p className="muted" style={{ fontSize: 12 }}>
          Use an approximate centre. Add one or more named campus areas
          afterwards.
        </p>
        {msg && <div className="alert error">{msg}</div>}
        <button
          className="btn primary"
          disabled={
            busy || !form.name.trim() || !form.latitude || !form.longitude
          }
          onClick={create}
        >
          {busy ? "Creating…" : "Create campus"}
        </button>
        <button className="btn" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  );
}
