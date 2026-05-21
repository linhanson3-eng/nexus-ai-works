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

function App() {
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
            <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}

export default App;
