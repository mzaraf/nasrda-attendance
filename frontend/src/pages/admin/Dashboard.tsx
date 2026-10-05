import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

const CARDS: [string, string][] = [
  ["total_staff", "Total staff"], ["present", "Present"], ["late", "Late"], ["absent", "Absent"],
  ["on_site", "On-site now"], ["checked_out", "Checked out"], ["official_duty", "Official duty"],
  ["on_leave", "On leave"],
];
const time = (iso?: string) =>
  iso ? new Intl.DateTimeFormat("en-NG", { hour: "numeric", minute: "2-digit", timeZone: "Africa/Lagos" }).format(new Date(iso)) : "—";

export default function AdminDashboard() {
  const stats = useQuery({ queryKey: ["dash"], queryFn: () => api.get("/admin/dashboard/").then((r) => r.data), refetchInterval: 15_000 });
  const live = useQuery({ queryKey: ["live"], queryFn: () => api.get("/admin/attendance/").then((r) => r.data as any[]), refetchInterval: 15_000 });

  return (
    <div className="page wide">
      <h2>Today's attendance</h2>
      {stats.data?.non_working_reason && <div className="alert success">Office closed today. {stats.data.non_working_reason} No staff are counted as absent.</div>}
      <div className="stats">
        {CARDS.map(([k, label]) => (
          <div className="stat" key={k}><b>{stats.data?.[k] ?? "…"}</b><small>{label}</small></div>
        ))}
      </div>
      <h3>Live board</h3>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Staff</th><th>Department</th><th>In</th><th>Out</th><th>Status</th><th>Campus</th><th></th></tr></thead>
          <tbody>
            {live.data?.map((r) => (
              <tr key={r.id}>
                <td>{r.name}<small>{r.ippis}</small></td><td>{r.department}</td>
                <td>{time(r.check_in_at)}</td><td>{time(r.check_out_at)}</td>
                <td>{r.status === "late" ? "🔴 Late" : "🟢 Present"}</td><td>{r.campus}</td>
                <td>{r.review === "review_required" && <span className="pill review">REVIEW REQUIRED</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
