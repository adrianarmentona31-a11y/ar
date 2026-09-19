import React from "react";
import "@/App.css";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider } from "@/context/AuthContext";
import { I18nProvider } from "@/context/I18nContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppShell } from "@/components/AppShell";

import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import ModulePlaceholder from "@/pages/ModulePlaceholder";

function ProtectedShell({ children }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}

const FUTURE_MODULES = [
  "clientes",
  "vehiculos",
  "servicios",
  "cotizaciones",
  "cobros",
  "finanzas",
  "tecnicos",
  "empresas",
  "configuracion",
];

export default function App() {
  return (
    <div className="App">
      <I18nProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route
                path="/control"
                element={
                  <ProtectedShell>
                    <Dashboard />
                  </ProtectedShell>
                }
              />
              {FUTURE_MODULES.map((m) => (
                <Route
                  key={m}
                  path={`/${m}`}
                  element={
                    <ProtectedShell>
                      <ModulePlaceholderRoute moduleKey={m} />
                    </ProtectedShell>
                  }
                />
              ))}
              <Route path="/" element={<Navigate to="/control" replace />} />
              <Route path="*" element={<Navigate to="/control" replace />} />
            </Routes>
          </BrowserRouter>
          <Toaster
            theme="dark"
            position="top-right"
            toastOptions={{
              style: {
                background: "#101010",
                border: "1px solid #262626",
                color: "#fff",
              },
            }}
          />
        </AuthProvider>
      </I18nProvider>
    </div>
  );
}

// tiny wrapper so useParams is not needed here
function ModulePlaceholderRoute({ moduleKey }) {
  return <ModulePlaceholder key={moduleKey} moduleKeyOverride={moduleKey} />;
}
