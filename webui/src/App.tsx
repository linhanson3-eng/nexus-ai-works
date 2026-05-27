import { useState, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import { ToastProvider } from "./components/Toast";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { AuthPage } from "./components/AuthPage";
import { Settings } from "./components/Settings";
import { AuthProvider, useAuth } from "./lib/AuthContext";
import { ArtifactProvider } from "./lib/ArtifactContext";
import { api } from "./lib/api";
import { Onboarding } from "./components/Onboarding";
import { PANEL_REGISTRY } from "./lib/panels";

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

const panelRoutes = Object.values(PANEL_REGISTRY).map((panel) => {
  const PanelComponent = panel.element;
  return (
    <Route
      key={panel.id}
      path={panel.route.replace("/", "")}
      element={
        <ErrorBoundary>
          <Suspense fallback={
            <div className="flex items-center justify-center h-full min-h-[200px]">
              <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
            </div>
          }>
            <PanelComponent />
          </Suspense>
        </ErrorBoundary>
      }
    />
  );
});

function AppRoutes() {
  const [showOnboarding, setShowOnboarding] = useState(
    !localStorage.getItem("nexus_onboarding_done"),
  );

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
          {panelRoutes}
          <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
    </>
  );
}

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <ArtifactProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </ArtifactProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;
