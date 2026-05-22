import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { Settings } from "./components/Settings";
import { ChatPanel } from "./components/ChatPanel";
import { Dashboard } from "./components/Dashboard";
import { WorkshopList } from "./components/WorkshopList";
import { KanbanBoard } from "./components/KanbanBoard";
import { WorkflowList } from "./components/WorkflowList";
import { ChainList } from "./components/ChainList";
import { ModuleFactory } from "./components/ModuleFactory";
import { TemplateLibrary } from "./components/TemplateLibrary";
import { Marketplace } from "./components/Marketplace";
import { fetchCsrfToken } from "./lib/api";

function App() {
  useEffect(() => {
    fetchCsrfToken();
  }, []);
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ErrorBoundary><ChatPanel /></ErrorBoundary>} />
            <Route path="/dashboard" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
            <Route path="/workshops" element={<ErrorBoundary><WorkshopList /></ErrorBoundary>} />
            <Route path="/kanban" element={<ErrorBoundary><KanbanBoard /></ErrorBoundary>} />
            <Route path="/workflows" element={<ErrorBoundary><WorkflowList /></ErrorBoundary>} />
            <Route path="/chains" element={<ErrorBoundary><ChainList /></ErrorBoundary>} />
            <Route path="/factory" element={<ErrorBoundary><ModuleFactory /></ErrorBoundary>} />
            <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
            <Route path="/library" element={<ErrorBoundary><TemplateLibrary /></ErrorBoundary>} />
            <Route path="/market" element={<ErrorBoundary><Marketplace /></ErrorBoundary>} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}

export default App;
