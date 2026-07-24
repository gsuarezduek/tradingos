"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Blocks,
  LineChart,
  FlaskConical,
  SlidersHorizontal,
  Compass,
  Dice5,
  ShieldAlert,
  NotebookPen,
  PieChart,
  FileStack,
  Bot,
  Settings,
  type LucideIcon,
} from "lucide-react";

const modules: { label: string; icon: LucideIcon; href?: string }[] = [
  { label: "Constructor de Estrategias", icon: Blocks },
  { label: "Backtesting", icon: LineChart },
  { label: "Laboratorio de Estrategias", icon: FlaskConical },
  { label: "Optimizador", icon: SlidersHorizontal, href: "/optimizador" },
  { label: "Clasificador de Mercado", icon: Compass },
  { label: "Simulación Monte Carlo", icon: Dice5, href: "/montecarlo" },
  { label: "Gestión de Riesgo", icon: ShieldAlert },
  { label: "Journal de Trading", icon: NotebookPen },
  { label: "Portfolio de Estrategias", icon: PieChart },
  { label: "Paper Trading", icon: FileStack },
  { label: "Trading Automático", icon: Bot },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-72 shrink-0 border-r border-border bg-surface p-6 lg:flex lg:flex-col">
      <div className="flex items-center gap-2 px-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-sm font-bold text-white">
          T
        </div>
        <span className="text-lg font-bold tracking-tight">Trading OS</span>
      </div>

      <nav className="mt-8 flex flex-col gap-1">
        <Link
          href="/"
          className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold ${
            pathname === "/" ? "bg-panel text-ink" : "text-muted hover:text-ink"
          }`}
        >
          <LayoutDashboard size={18} />
          Dashboard
        </Link>
      </nav>

      <div className="mt-8 px-2 text-xs font-semibold uppercase tracking-wide text-muted">
        Módulos
      </div>
      <nav className="mt-2 flex flex-col gap-1">
        {modules.map(({ label, icon: Icon, href }) => {
          if (href) {
            const active = pathname === href;
            return (
              <Link
                key={label}
                href={href}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold ${
                  active ? "bg-panel text-ink" : "text-muted hover:text-ink"
                }`}
              >
                <Icon size={18} className="shrink-0" />
                <span className="flex-1">{label}</span>
              </Link>
            );
          }
          return (
            <div
              key={label}
              className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted"
              title="Próximamente"
            >
              <Icon size={18} className="shrink-0" />
              <span className="flex-1">{label}</span>
              <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium">
                Pronto
              </span>
            </div>
          );
        })}
      </nav>

      <div className="mt-auto pt-8">
        <div
          className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted"
          title="Próximamente"
        >
          <Settings size={18} />
          <span className="flex-1">Configuración</span>
          <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium">
            Pronto
          </span>
        </div>
      </div>
    </aside>
  );
}
