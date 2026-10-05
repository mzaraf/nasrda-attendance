import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, errorOf } from "../../api";

type Campus = { id: number; name: string };
type Department = { id: number; name: string; campus_ids?: number[] };

export default function Reports() {
  const [report, setReport] = useState("daily");
  const [format, setFormat] = useState("xlsx");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [campus, setCampus] = useState("");
  const [department, setDepartment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { data: scope } = useQuery({ queryKey: ["report-scope"], queryFn: () => api.get("/reports/scope/").then((r) => r.data as { all_access: boolean; campuses: Campus[]; departments: Department[] }) });
  const campuses = scope?.campuses ?? [];
  const departments = scope?.departments ?? [];
  const restricted = scope?.all_access === false;
  const selectedCampus = restricted ? String(campuses[0]?.id ?? "") : campus;
  const selectedDepartment = restricted ? String(departments[0]?.id ?? "") : department;

  const download = async () => {
    const params = new URLSearchParams({ report, output_format: format, ...(report === "monthly" ? { month: date.slice(0, 7) } : { date }), ...(selectedCampus ? { campus: selectedCampus } : {}), ...(selectedDepartment ? { department: selectedDepartment } : {}) });
    setBusy(true); setError("");
    try {
      const response = await api.get(`/reports/export/?${params.toString()}`, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      const selected = new Date(`${report === "monthly" ? date.slice(0, 7) + "-01" : date}T00:00:00`);
      const period = report === "monthly"
        ? new Intl.DateTimeFormat("en-NG", { month: "short", year: "numeric" }).format(selected).replace(/\s+/g, "-")
        : new Intl.DateTimeFormat("en-NG", { day: "2-digit", month: "short", year: "numeric" }).format(selected).replace(/\s+/g, "-");
      const reportName = report === "monthly" ? "monthly-attendance-summary" : "daily-attendance";
      const campusName = campuses.find((item) => item.id === Number(selectedCampus))?.name ?? "All-Campuses";
      const departmentName = departments.find((item) => item.id === Number(selectedDepartment))?.name ?? "All-Departments";
      const safe = (value: string) => value.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "");
      link.download = `${reportName}-${safe(campusName)}-${safe(departmentName)}-${period}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      // Axios returns errors as Blob when responseType is blob; decode those so the
      // user sees the API's actual message rather than an empty failed download.
      if (e?.response?.data instanceof Blob) {
        try {
          const payload = JSON.parse(await e.response.data.text());
          setError(payload.message ?? payload.detail ?? "Could not generate the report.");
        } catch { setError("Could not generate the report. Please try again."); }
      } else setError(errorOf(e).message);
    } finally { setBusy(false); }
  };
  const availableDepartments = selectedCampus ? departments.filter((item) => item.campus_ids?.includes(Number(selectedCampus))) : departments;

  return (
    <div className="page">
      <h2>Reports</h2>
      <div className="card">
        <label>Report</label>
        <select value={report} onChange={(e) => setReport(e.target.value)}>
          <option value="daily">Daily attendance</option>
          <option value="monthly">Monthly summary</option>
        </select>
        <label>{report === "monthly" ? "Month" : "Date"}</label>
        <input type={report === "monthly" ? "month" : "date"} value={report === "monthly" ? date.slice(0, 7) : date} onChange={(e) => setDate(report === "monthly" ? `${e.target.value}-01` : e.target.value)} />
        <div className="row report-filters">
          <div><label>Campus</label><select value={selectedCampus} disabled={restricted} onChange={(e) => { setCampus(e.target.value); setDepartment(""); }}><option value="">All campuses</option>{campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
          <div><label>Department</label><select value={selectedDepartment} disabled={restricted} onChange={(e) => setDepartment(e.target.value)}><option value="">All departments</option>{availableDepartments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
        </div>
        <small className="muted">{restricted ? "Directors can generate reports only for their assigned campus and department." : "Select a campus to limit the department list, or leave either filter on All."}</small>
        <label>Format</label>
        <select value={format} onChange={(e) => setFormat(e.target.value)}>
          <option value="xlsx">Excel (.xlsx)</option>
          <option value="csv">CSV</option>
          <option value="pdf">PDF</option>
        </select>
        {error && <div className="alert error">{error}</div>}
        <button className="btn primary" disabled={busy} onClick={download}>{busy ? "Generating…" : "Generate report"}</button>
      </div>
    </div>
  );
}
