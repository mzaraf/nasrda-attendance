import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorOf } from "../api";

type Act = { id: number; category: number; title: string; description: string;
             start_time: string; end_time: string };
const blank = { category: "", title: "", description: "" };

export default function ActivitySheet(p: { busy: boolean; error?: string; onClose: () => void; onSubmit: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<any>(blank);
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");

  const cats = useQuery({ queryKey: ["cats"], queryFn: () => api.get("/activities/categories/").then((r) => r.data as any[]) });
  const acts = useQuery({ queryKey: ["acts"], queryFn: () => api.get("/activities/today/").then((r) => r.data as Act[]) });

  const add = useMutation({
    mutationFn: async () => {
      const { data } = await api.post("/activities/today/", { ...form, category: Number(form.category) });
      if (file) {
        const fd = new FormData(); fd.append("file", file);
        await api.post(`/activities/${data.id}/attachments/`, fd);
      }
    },
    onSuccess: () => { setForm(blank); setFile(null); setMsg(""); qc.invalidateQueries({ queryKey: ["acts"] }); qc.invalidateQueries({ queryKey: ["today"] }); },
    onError: (e) => setMsg(errorOf(e).message || "Check the form fields."),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/activities/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["acts"] }),
  });

  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });
  const valid = form.category && form.title.trim() && form.description.trim();
  const count = acts.data?.length ?? 0;

  return (
    <div className="sheet-backdrop" onClick={p.onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grab" />
        <h3>Daily Activity Report</h3>
        <p className="muted">Record today's activities before checking out.</p>

        {acts.data?.map((a) => (
          <div className="act" key={a.id}>
            <div><b>{a.title}</b></div>
            <button className="link" onClick={() => remove.mutate(a.id)}>Remove</button>
          </div>
        ))}

        <div className="card">
          <label>Category</label>
          <select value={form.category} onChange={set("category")}>
            <option value="">Select…</option>
            {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <label>Activity title</label>
          <input value={form.title} onChange={set("title")} />
          <label>Description</label>
          <textarea rows={3} value={form.description} onChange={set("description")} />
          <label>Supporting document (optional)</label>
          <input type="file" accept=".pdf,.docx,.xlsx,.jpg,.jpeg,.png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          {msg && <div className="alert error">{msg}</div>}
          <button className="btn" disabled={!valid || add.isPending} onClick={() => add.mutate()}>+ Add activity</button>
        </div>

        {p.error && <div className="alert error">{p.error}</div>}
        <div className="row sticky">
          <button className="btn" disabled={p.busy || add.isPending} onClick={p.onClose}>Cancel</button>
          <button className="btn primary" disabled={count === 0 || p.busy} onClick={p.onSubmit}>
            {p.busy ? "Checking out…" : `Submit ${count} ${count === 1 ? "activity" : "activities"} & check out`}
          </button>
        </div>
      </div>
    </div>
  );
}
