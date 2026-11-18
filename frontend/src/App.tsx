import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { useApp } from "./lib/app";
import Admin from "./pages/Admin";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import { MockHome, MockReport, MockRun } from "./pages/Mock";
import ModulePage from "./pages/ModulePage";
import Plans from "./pages/Plans";
import Settings from "./pages/Settings";
import TaskPage from "./pages/TaskPage";

function Protected({ children }: { children: ReactNode }) {
  const { user, ready } = useApp();
  const loc = useLocation();
  if (!ready)
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label="Loading" />
      </div>
    );
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return <AppLayout>{children}</AppLayout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Auth mode="login" />} />
      <Route path="/register" element={<Auth mode="register" />} />
      <Route path="/app" element={<Protected><Dashboard /></Protected>} />
      <Route path="/app/practice/:module" element={<Protected><ModulePage /></Protected>} />
      <Route path="/app/task/:task" element={<Protected><TaskPage /></Protected>} />
      <Route path="/app/mock" element={<Protected><MockHome /></Protected>} />
      <Route path="/app/mock/:id" element={<Protected><MockRun /></Protected>} />
      <Route path="/app/mock/:id/report" element={<Protected><MockReport /></Protected>} />
      <Route path="/app/plans" element={<Protected><Plans /></Protected>} />
      <Route path="/app/settings" element={<Protected><Settings /></Protected>} />
      <Route path="/app/admin" element={<Protected><Admin /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
