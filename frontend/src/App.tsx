import { Suspense, lazy, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastContainer } from "@/components/ui/Toast";
import { Spinner } from "@/components/ui/Spinner";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/api/auth";

// Lazy-load heavy pages
const AuthPage = lazy(() => import("@/components/auth/AuthPage"));
const Dashboard = lazy(() => import("@/components/dashboard/Dashboard"));
const WorkspacePage = lazy(() => import("@/components/workspace/WorkspacePage"));

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
    mutations: { retry: 0 },
  },
});

function PageSpinner() {
  return (
    <div className="flex items-center justify-center h-screen bg-surface">
      <Spinner size="lg" />
    </div>
  );
}

function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? children : <Navigate to="/auth" replace />;
}

function AppInner() {
  const { isAuthenticated, setUser, clearAuth } = useAuthStore();

  // Rehydrate user on page load if token exists
  useEffect(() => {
    if (!isAuthenticated) return;
    authApi.me().then(setUser).catch(() => clearAuth());
  }, []);

  return (
    <Suspense fallback={<PageSpinner />}>
      <Routes>
        <Route
          path="/auth"
          element={isAuthenticated ? <Navigate to="/" replace /> : <AuthPage />}
        />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/workspace/:projectId"
          element={
            <RequireAuth>
              <WorkspacePage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AppInner />
        <ToastContainer />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
