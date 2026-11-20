import { lazy, useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { api } from "./api/client";
import type { User } from "./api/types";
import { AppLayout } from "./layouts/AppLayout";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import { useAuth } from "./stores";

const DashboardPage = lazy(() => import("./pages/dashboard/DashboardPage"));
const CategoriesPage = lazy(() => import("./pages/inventory/CategoriesPage"));
const CategoryDetailPage = lazy(() => import("./pages/inventory/CategoryDetailPage"));
const DesignDetailPage = lazy(() => import("./pages/inventory/DesignDetailPage"));
const StockPage = lazy(() => import("./pages/stock/StockPage"));
const InsightsPage = lazy(() => import("./pages/insights/InsightsPage"));
const PurchasesPage = lazy(() => import("./pages/plans/PurchasesPage"));
const SalesPage = lazy(() => import("./pages/sales/SalesPage"));
const NewBillPage = lazy(() => import("./pages/sales/NewBillPage"));
const BillDetailPage = lazy(() => import("./pages/sales/BillDetailPage"));
const PlanDetailPage = lazy(() => import("./pages/plans/PlanDetailPage"));
const ReportsPage = lazy(() => import("./pages/reports/ReportsPage"));
const SettingsPage = lazy(() => import("./pages/settings/SettingsPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { token, expiresAt } = useAuth();
  const location = useLocation();
  const expired = expiresAt ? new Date(expiresAt).getTime() < Date.now() : false;
  if (!token || expired) {
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }
  return <>{children}</>;
}

function useValidateSession() {
  const { token, expiresAt, clear, setAuth, remember } = useAuth();
  useEffect(() => {
    if (!token) return;
    if (expiresAt && new Date(expiresAt).getTime() < Date.now()) {
      clear();
      return;
    }
    api<User>("/auth/me")
      .then((u) => setAuth(token, expiresAt ?? "", u, remember))
      .catch(() => undefined);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}

export default function App() {
  useValidateSession();
  const token = useAuth((s) => s.token);
  return (
    <Routes>
      <Route path="/" element={token ? <Navigate to="/app" replace /> : <LandingPage />} />
      <Route path="/login/owner" element={<LoginPage role="OWNER" />} />
      <Route path="/login/admin" element={<LoginPage role="ADMIN" />} />
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="inventory" element={<CategoriesPage />} />
        <Route path="inventory/:categoryId" element={<CategoryDetailPage />} />
        <Route path="designs/:designId" element={<DesignDetailPage />} />
        <Route path="stock" element={<StockPage />} />
        <Route path="insights" element={<InsightsPage />} />
        <Route path="sales" element={<SalesPage />} />
        <Route path="sales/new" element={<NewBillPage />} />
        <Route path="sales/bills/:billId" element={<BillDetailPage />} />
        <Route path="purchase-plans" element={<PurchasesPage />} />
        <Route path="purchase-plans/:planId" element={<PlanDetailPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
