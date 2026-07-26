import Link from "next/link";
import { Calendar, TrendingDown, TrendingUp } from "lucide-react";
import { CATEGORY_LABELS, type SavedStrategySummary } from "@/app/estrategias/EstrategiasClient";

function StrategyCard({ strategy }: { strategy: SavedStrategySummary }) {
  const run = strategy.latest_run;
  return (
    <Link
      href={`/estrategias/${strategy.id}`}
      className="block rounded-2xl border border-border bg-surface p-4 transition-colors hover:border-ink"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{strategy.name}</h3>
        <span className="shrink-0 rounded-full border border-border px-2 py-0.5 text-[10px] font-medium text-muted">
          {CATEGORY_LABELS[strategy.category] ?? strategy.category}
        </span>
      </div>
      <p className="mt-2 text-xs text-muted">
        {strategy.symbols.join(", ")} · {strategy.timeframes.join(", ")}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted">
        <span className="flex items-center gap-1">
          <Calendar size={13} />
          {new Date(strategy.updated_at).toLocaleDateString("es-AR")}
        </span>
        {run ? (
          <>
            <span className="flex items-center gap-1">
              <TrendingUp size={13} />
              PF {run.metrics.profit_factor.toFixed(2)}
            </span>
            <span className="flex items-center gap-1">
              <TrendingDown size={13} />
              DD {(run.metrics.max_drawdown * 100).toFixed(1)}%
            </span>
          </>
        ) : (
          <span>Sin backtest corrido todavía</span>
        )}
      </div>
    </Link>
  );
}

export function ActiveStrategiesGrid({ strategies }: { strategies: SavedStrategySummary[] }) {
  if (strategies.length === 0) {
    return (
      <div className="mt-4 rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted">
        No tenés estrategias activas.{" "}
        <Link href="/estrategias" className="font-semibold text-ink underline">
          Creá una en Estrategias
        </Link>
        .
      </div>
    );
  }

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {strategies.map((strategy) => (
        <StrategyCard key={strategy.id} strategy={strategy} />
      ))}
    </div>
  );
}
