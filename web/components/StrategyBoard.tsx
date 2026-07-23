import { ArrowUpDown, Calendar, TrendingDown, TrendingUp } from "lucide-react";
import { strategies, strategyColumns, type DummyStrategy } from "@/lib/dummy-data";

function StrategyCard({ strategy }: { strategy: DummyStrategy }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{strategy.name}</h3>
        <span className="shrink-0 rounded-full border border-border px-2 py-0.5 text-[10px] font-medium text-muted">
          {strategy.symbol} · {strategy.timeframe}
        </span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">{strategy.description}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted">
        <span className="flex items-center gap-1">
          <Calendar size={13} />
          {strategy.updatedAt}
        </span>
        <span className="flex items-center gap-1">
          <TrendingUp size={13} />
          PF {strategy.profitFactor.toFixed(2)}
        </span>
        <span className="flex items-center gap-1">
          <TrendingDown size={13} />
          DD {strategy.maxDrawdownPct.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export function StrategyBoard() {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
      {strategyColumns.map((column) => {
        const items = strategies.filter((s) => s.status === column.key);
        return (
          <div key={column.key}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-ink">{column.label}</h2>
              <span className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-muted">
                {items.length}
                <ArrowUpDown size={12} />
              </span>
            </div>
            <div className="mt-4 flex flex-col gap-3">
              {items.map((strategy) => (
                <StrategyCard key={strategy.id} strategy={strategy} />
              ))}
              {items.length === 0 && (
                <div className="rounded-2xl border border-dashed border-border p-4 text-center text-xs text-muted">
                  Sin estrategias en esta columna
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
