import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { AllContests } from "@/pages/AllContests";
import { AnalyticsPage } from "@/pages/Analytics";
import { ContestDetail } from "@/pages/ContestDetail";
import { Discover } from "@/pages/Discover";
import { Entering } from "@/pages/Entering";
import { Overview } from "@/pages/Overview";
import { Runs } from "@/pages/Runs";
import { SettingsPage } from "@/pages/Settings";
import { Shortlist } from "@/pages/Shortlist";
import { SourcesPage } from "@/pages/Sources";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="discover" element={<Discover />} />
        <Route path="contests" element={<AllContests />} />
        <Route path="contests/:key" element={<ContestDetail />} />
        <Route path="shortlist" element={<Shortlist />} />
        <Route path="entering" element={<Entering />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="runs" element={<Runs />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
