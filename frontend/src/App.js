import React from "react";
import "@/App.css";
import "@/receipt.css";
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
import Clientes from "@/pages/Clientes";
import Vehiculos from "@/pages/Vehiculos";
import Servicios from "@/pages/Servicios";
import Cotizaciones from "@/pages/Cotizaciones";
import Cobros from "@/pages/Cobros";
import Finanzas from "@/pages/Finanzas";
import Tecnicos from "@/pages/Tecnicos";
import Empresas from "@/pages/Empresas";
import Configuracion from "@/pages/Configuracion";
import Recibo from "@/pages/Recibo";
import Notas from "@/pages/Notas";
import Transferencia from "@/pages/Transferencia";

function ProtectedShell({ children }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}

const ROUTES = [
  { path: "/control", el: <Dashboard /> },
  { path: "/clientes", el: <Clientes /> },
  { path: "/vehiculos", el: <Vehiculos /> },
  { path: "/servicios", el: <Servicios /> },
  { path: "/cotizaciones", el: <Cotizaciones /> },
  { path: "/cobros", el: <Cobros /> },
  { path: "/finanzas", el: <Finanzas /> },
  { path: "/tecnicos", el: <Tecnicos /> },
  { path: "/empresas", el: <Empresas /> },
  { path: "/configuracion", el: <Configuracion /> },
  { path: "/recibo/:kind/:id", el: <Recibo /> },
  { path: "/notas", el: <Notas /> },
  { path: "/transferencia", el: <Transferencia /> },
];

export default function App() {
  return (
    <div className="App">
      <I18nProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              {ROUTES.map((r) => (
                <Route key={r.path} path={r.path} element={<ProtectedShell>{r.el}</ProtectedShell>} />
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
