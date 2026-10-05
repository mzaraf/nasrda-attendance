import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export default function AuditLog() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const { data } = useQuery({
    queryKey: ["audit", action, page],
    queryFn: () => api.get("/admin/audit-logs/", { params: { action, page } }).then((r) => r.data),
  });
  const entries = data?.results ?? [];
  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 100));

  return (
    <div className="page wide">
      <h2>System audit log</h2>
      <input className="audit-filter" placeholder="Filter by action (e.g. attendance.check_in)" value={action}
             onChange={(e) => { setAction(e.target.value); setPage(1); }} />
      <div className="table-wrap audit-table-wrap">
        <table>
          <thead><tr><th>When</th><th>User</th><th>Action</th><th>Description</th><th>IP</th></tr></thead>
          <tbody>
            {entries.map((e: any) => (
              <tr key={e.id}>
                <td>{new Date(e.created_at).toLocaleString("en-NG", { timeZone: "Africa/Lagos" })}</td>
                <td>{e.user}</td><td>{e.action}</td><td>{e.description}</td><td>{e.ip_address}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {total > 0 && <div className="audit-pagination" aria-label="Audit log pagination">
        <small>{total} log entries · Page {page} of {totalPages}</small>
        <div><button className="btn" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="btn" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>Next</button></div>
      </div>}
    </div>
  );
}
