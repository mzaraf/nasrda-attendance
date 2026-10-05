import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type Me = {
  authenticated: boolean; name: string; first_name: string; last_name: string; ippis_number: string;
  department: string | null; can_admin: boolean; can_manage_staff: boolean; can_view_staff: boolean; can_access_staff: boolean; can_approve: boolean;
  can_manage_devices: boolean; can_access_approvals: boolean; can_export_reports: boolean; can_view_audit: boolean; can_manage_geofence: boolean; can_manage_roles: boolean;
  can_review_department_requests: boolean;
  has_device: boolean; require_passkey: boolean; mfa_enabled: boolean; mfa_configured: boolean;
};
type Ctx = { me?: Me; loading: boolean; refresh: () => void; adoptSession: (me: Me) => Promise<void>; logout: () => Promise<void> };
const AuthCtx = createContext<Ctx>(null!);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [sessionIdentity, setSessionIdentity] = useState<Me | undefined>();
  const fetchMe = () => api.get("/auth/me/").then((r) => r.data as Me);
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
  });
  // This state, rather than a pending query-cache response, controls which shell
  // and navigation permissions are shown immediately after an account switch.
  const me = sessionIdentity ?? data;
  const refresh = () => { void refetch().then((result) => { if (result.data) setSessionIdentity(result.data); }); };
  const adoptSession = async (identity: Me) => {
    await qc.cancelQueries({ queryKey: ["me"] });
    qc.setQueryData(["me"], identity);
    setSessionIdentity(identity);
  };
  const logout = async () => {
    try { await api.post("/auth/logout/"); }
    catch { /* An expired/offline session should still return the user to the login screen. */ }
    finally {
      await qc.cancelQueries();
      qc.clear();                                        // drop all cached data (attendance, staff lists, etc.)
      const anonymous = { authenticated: false } as Me;
      qc.setQueryData(["me"], anonymous);
      setSessionIdentity(anonymous);                      // remove prior account navigation immediately
    }
  };
  return <AuthCtx.Provider value={{ me, loading: sessionIdentity === undefined ? isLoading : false, refresh, adoptSession, logout }}>{children}</AuthCtx.Provider>;
}
