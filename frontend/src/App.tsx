import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { DemoBar } from "@/components/DemoBar";
import { Shell } from "@/components/Shell";
import { getSession } from "@/auth/store";
import { Login } from "@/pages/Login";
import { Scenarios } from "@/pages/Scenarios";
import { Overview } from "@/pages/Overview";
import { Transparency } from "@/pages/Transparency";
import { MemorySearch } from "@/pages/MemorySearch";
import { Kpis } from "@/pages/Kpis";
import { CaseFile } from "@/pages/CaseFile";

function RequireAuth({ children }: { children: React.ReactElement }) {
  if (!getSession()) return <Navigate to="/login" replace />;
  return (
    <Shell>
      {children}
      <DemoBar />
    </Shell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/scenarios" element={<RequireAuth><Scenarios /></RequireAuth>} />
        <Route path="/app" element={<RequireAuth><Overview /></RequireAuth>} />
        <Route path="/kpis" element={<RequireAuth><Kpis /></RequireAuth>} />
        <Route path="/kpis/:kpiId" element={<RequireAuth><CaseFile /></RequireAuth>} />
        <Route path="/transparency" element={<RequireAuth><Transparency /></RequireAuth>} />
        <Route path="/memory" element={<RequireAuth><MemorySearch /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/scenarios" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

