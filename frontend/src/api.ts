import axios from "axios";

const csrf = () =>
  document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1] ?? "";

export const api = axios.create({ baseURL: "/api", withCredentials: true });
api.interceptors.request.use((cfg) => {
  cfg.headers["X-CSRFToken"] = csrf();
  return cfg;
});

export type ApiError = { code: string; message: string };

// Two shapes come back from the backend: our own DomainError responses ({code, message} — see
// apps/core/errors.py), and DRF's default serializer validation errors ({field: ["msg", ...]} or
// {"detail": "msg"}), which every ModelViewSet raises automatically and which don't have a `code`.
// Without handling the second shape, any plain validation failure (e.g. a bad geofence polygon,
// a duplicate campus name) fell through to a generic "Something went wrong" — which reads exactly
// like a crash even though the server responded correctly with a specific, useful message.
export const errorOf = (e: any): ApiError => {
  const data = e?.response?.data;
  if (data?.code) return data;
  if (data && typeof data === "object") {
    if (typeof data.detail === "string") return { code: "VALIDATION", message: data.detail };
    const parts = Object.entries(data).flatMap(([field, msgs]) =>
      (Array.isArray(msgs) ? msgs : [msgs]).map((m) => (field === "non_field_errors" ? String(m) : `${field}: ${m}`))
    );
    if (parts.length) return { code: "VALIDATION", message: parts.join(" ") };
  }
  if (!navigator.onLine || e?.code === "ERR_NETWORK")
    return { code: "OFFLINE", message: "Internet connection is required to verify and record attendance." };
  return { code: e?.code ?? "UNKNOWN", message: e?.message ?? "Something went wrong. Please try again." };
};