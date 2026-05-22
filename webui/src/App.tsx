import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { AuthPage } from "./components/AuthPage";
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
import { AuthProvider, useAuth } from "./lib/AuthContext";
import { fetchCsrfToken, api } from "./lib/api";
import { Onboarding } from "./components/Onboarding";
import { useState } from "react";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[300px]">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" replace />;
  }

  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[300px]">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  const [showOnboarding, setShowOnboarding] = useState(
    !localStorage.getItem("nexus_onboarding_done"),
  );

  useEffect(() => {
    fetchCsrfToken();
  }, []);

  const finishOnboarding = () => {
    localStorage.setItem("nexus_onboarding_done", "1");
    setShowOnboarding(false);
    api.savePreferences({ onboarding_done: true }).catch(() => {});
  };

  return (
    <>
      {showOnboarding && <Onboarding onDone={finishOnboarding} />}
      <Routes>
        <Route path="/auth" element={<PublicRoute><AuthPage /></PublicRoute>} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
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
    </>
  );
}

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  );
}

export default App;
