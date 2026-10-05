import { useState } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./auth";
import Login from "./pages/Login";
import Home from "./pages/Home";
import History from "./pages/History";
import DeviceSetup from "./pages/DeviceSetup";
import Requests from "./pages/Requests";
import Profile from "./pages/Profile";
import AdminDashboard from "./pages/admin/Dashboard";
import StaffManagement from "./pages/admin/StaffManagement";
import Approvals from "./pages/admin/Approvals";
import Reports from "./pages/admin/Reports";
import AuditLog from "./pages/admin/AuditLog";
import GeofenceEditor from "./pages/admin/GeofenceEditor";
import RolesManagement from "./pages/admin/RolesManagement";
import Settings from "./pages/admin/Settings";
import Departments from "./pages/admin/Departments";
import Holidays from "./pages/admin/Holidays";
import "./styles.css";

// Keep the active screen stable when a staff member switches apps or returns to the browser.
// Queries are still refreshed after the actions that change their data (check-in, approvals,
// edits, etc.), but should not redraw the page merely because the window regains focus.
const qc = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });

// Shared between the mobile tab bar and the desktop sidebar so the two navs can't drift out of sync.
const STAFF_LINKS = [
  { to: "/", end: true, icon: "🏠", label: "Home" },
  { to: "/history", icon: "🗓️", label: "History" },
  { to: "/device", icon: "🔐", label: "Device" },
  { to: "/requests", icon: "📝", label: "Requests" },
  { to: "/profile", icon: "🔑", label: "Change password" },
];
const ADMIN_LINKS = [
  { to: "/admin", end: true, icon: "📊", label: "Dashboard", access: "can_admin" },
  { to: "/admin/staff", icon: "🧑‍🤝‍🧑", label: "Staff", access: "can_access_staff" },
  { to: "/admin/departments", icon: "🏢", label: "Departments", access: "can_manage_staff" },
  { to: "/admin/roles", icon: "🛡️", label: "Roles", access: "can_manage_roles" },
  { to: "/admin/settings", icon: "⚙️", label: "Settings", access: "can_manage_roles" },
  { to: "/admin/holidays", icon: "📅", label: "Holidays", access: "can_manage_roles" },
  { to: "/admin/approvals", icon: "✅", label: "Approvals", access: "can_access_approvals" },
  { to: "/admin/reports", icon: "📄", label: "Reports", access: "can_export_reports" },
  { to: "/admin/audit", icon: "📜", label: "Audit log", access: "can_view_audit" },
  { to: "/admin/geofence", icon: "🗺️", label: "Geofences", access: "can_manage_geofence" },
];

function Sidebar({ links, onLogout }: { links: typeof ADMIN_LINKS; onLogout: () => void }) {
  return (
    <nav className="sidebar">
      <div className="brand-mini"><img src="/logo.png" alt="" /><b>Staff Attendance System</b></div>
      {STAFF_LINKS.map((l) => <NavLink key={l.to} to={l.to} end={l.end}>{l.icon}<span>{l.label}</span></NavLink>)}
      {links.length > 0 && (
        <>
          <div className="section-label">Administration</div>
          {links.map((l) => <NavLink key={l.to} to={l.to} end={l.end}>{l.icon}<span>{l.label}</span></NavLink>)}
        </>
      )}
      <div style={{ flex: 1 }} />
      <button onClick={onLogout}>🚪<span>Sign out</span></button>
    </nav>
  );
}

function TabBar({ canAdmin, onLogout }: { canAdmin: boolean; onLogout: () => void }) {
  // Phones/tablets stay staff-focused: Home, History, Device, then one Admin entry point if applicable.
  return (
    <nav className="tabbar">
      <NavLink to="/" end>🏠<span>Home</span></NavLink>
      <NavLink to="/history">🗓️<span>History</span></NavLink>
      <NavLink to="/device">🔐<span>Device</span></NavLink>
      <NavLink to="/requests">📝<span>Requests</span></NavLink>
      <NavLink to="/profile">🔑<span>Password</span></NavLink>
      {canAdmin && <NavLink to="/admin">📊<span>Admin</span></NavLink>}
      <button onClick={onLogout}>🚪<span>Sign out</span></button>
    </nav>
  );
}

function Shell() {
  const { me, loading, logout } = useAuth();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);
  if (loading && !signingOut) return <div className="splash">NASRDA</div>;
  if (signingOut || !me?.authenticated) return <Routes><Route path="/login" element={<Login onAuthenticated={() => setSigningOut(false)} />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes>;

  // Wrapping here (rather than calling `logout` directly from the nav buttons) is what actually
  // sends the browser back to "/" after sign-out — logout() only clears auth state, it doesn't
  // touch the URL, so without this a sign-out from e.g. /admin/staff would clear the session but
  // leave the address bar (and back button) pointing at a page that no longer renders anything.
  const handleLogout = async () => {
    // Remove the entire authenticated shell immediately, including the sidebar/tab bar.
    setSigningOut(true);
    await logout();
    navigate("/login", { replace: true });
  };
  const adminLinks = ADMIN_LINKS.filter((link) => !!me[link.access as keyof typeof me]);

  return (
    <div className="app">
      <Sidebar links={adminLinks} onLogout={handleLogout} />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/history" element={<History />} />
          <Route path="/device" element={<DeviceSetup />} />
          <Route path="/requests" element={<Requests />} />
          <Route path="/profile" element={<Profile />} />
          {me.can_admin && <Route path="/admin" element={<AdminDashboard />} />}
          {me.can_access_staff && <Route path="/admin/staff" element={<StaffManagement />} />}
          {me.can_manage_staff && <Route path="/admin/departments" element={<Departments />} />}
          {me.can_manage_roles && <Route path="/admin/roles" element={<RolesManagement />} />}
          {me.can_manage_roles && <Route path="/admin/settings" element={<Settings />} />}
          {me.can_manage_roles && <Route path="/admin/holidays" element={<Holidays />} />}
          {me.can_access_approvals && <Route path="/admin/approvals" element={<Approvals />} />}
          {me.can_export_reports && <Route path="/admin/reports" element={<Reports />} />}
          {me.can_view_audit && <Route path="/admin/audit" element={<AuditLog />} />}
          {me.can_manage_geofence && <Route path="/admin/geofence" element={<GeofenceEditor />} />}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
      <TabBar canAdmin={!!me.can_admin} onLogout={handleLogout} />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider><BrowserRouter><Shell /></BrowserRouter></AuthProvider>
    </QueryClientProvider>
  );
}
