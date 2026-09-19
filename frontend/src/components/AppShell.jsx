import React from "react";
import { Header } from "./Header";
import { Sidebar, BottomNav } from "./Navigation";

export function AppShell({ children }) {
  return (
    <div className="min-h-screen bg-obsidian-mesh text-white flex flex-col">
      <Header />
      <div className="flex-1 flex w-full max-w-7xl mx-auto">
        <Sidebar />
        <main
          className="flex-1 px-4 sm:px-6 lg:px-8 py-5 sm:py-7 pb-24 lg:pb-10 w-full min-w-0"
          data-testid="app-main"
        >
          {children}
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
