import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({ children }) {
  const { isAuthenticated, isInitializing } = useAuth();

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-obsidian-mesh flex items-center justify-center">
        <div className="flex flex-col items-center gap-3" data-testid="auth-boot-loader">
          <div className="spinner spinner-gold" />
          <span className="font-mono-tactical text-xs tracking-widest text-zinc-500">
            ARMENTA OS · BOOTING
          </span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
