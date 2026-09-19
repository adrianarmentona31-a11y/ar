import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Car,
  Wrench,
  FileText,
  Wallet,
  LineChart,
  HardHat,
  Building2,
  Settings,
  MessageSquareHeart,
} from "lucide-react";
import { useI18n } from "../context/I18nContext";

export const NAV_ITEMS = [
  { key: "control", to: "/control", icon: LayoutDashboard, testId: "nav-item-control", enabled: true },
  { key: "clientes", to: "/clientes", icon: Users, testId: "nav-item-clientes", enabled: true },
  { key: "vehiculos", to: "/vehiculos", icon: Car, testId: "nav-item-vehiculos", enabled: true },
  { key: "servicios", to: "/servicios", icon: Wrench, testId: "nav-item-servicios", enabled: true },
  { key: "cotizaciones", to: "/cotizaciones", icon: FileText, testId: "nav-item-cotizaciones", enabled: true },
  { key: "cobros", to: "/cobros", icon: Wallet, testId: "nav-item-cobros", enabled: true },
  { key: "finanzas", to: "/finanzas", icon: LineChart, testId: "nav-item-finanzas", enabled: true },
  { key: "tecnicos", to: "/tecnicos", icon: HardHat, testId: "nav-item-tecnicos", enabled: true },
  { key: "empresas", to: "/empresas", icon: Building2, testId: "nav-item-empresas", enabled: true },
  { key: "encuestas", to: "/encuestas", icon: MessageSquareHeart, testId: "nav-item-encuestas", enabled: true },
  { key: "configuracion", to: "/configuracion", icon: Settings, testId: "nav-item-configuracion", enabled: true },
];

export function Sidebar() {
  const { t } = useI18n();
  return (
    <aside
      className="hidden lg:flex flex-col w-60 shrink-0 border-r border-[#1f1f1f] bg-[#070707] px-3 py-5 gap-1"
      data-testid="desktop-sidebar-nav"
    >
      <div className="px-3 pb-3 mb-2 border-b border-[#1a1a1a]">
        <span className="font-mono-tactical text-[10px] uppercase tracking-widest text-zinc-500">
          Panel operativo
        </span>
      </div>
      {NAV_ITEMS.map(({ key, to, icon: Icon, testId, enabled }) => (
        <NavLink
          key={key}
          to={to}
          data-testid={testId}
          className={({ isActive }) =>
            `sidebar-item ${isActive ? "active" : ""}`
          }
        >
          <Icon size={16} />
          <span className="flex-1">{t.nav[key]}</span>
          {!enabled && (
            <span className="text-[9px] font-mono-tactical uppercase tracking-widest text-zinc-600">
              soon
            </span>
          )}
        </NavLink>
      ))}
    </aside>
  );
}

export function BottomNav() {
  const { t } = useI18n();
  const primary = NAV_ITEMS.slice(0, 5);

  return (
    <nav
      className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-[#1f1f1f] bg-[#070707]/95 backdrop-blur-md"
      data-testid="mobile-bottom-nav"
    >
      <div className="flex items-stretch justify-between px-2 py-2">
        {primary.map(({ key, to, icon: Icon, testId }) => (
          <NavLink
            key={key}
            to={to}
            data-testid={testId}
            className={({ isActive }) =>
              `bottom-nav-item ${isActive ? "active" : ""}`
            }
          >
            <Icon size={20} />
            <span>{t.nav[key]}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
