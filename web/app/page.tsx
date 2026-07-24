import { DataBadge } from "@/components/DataBadge";
import { TopMetricsPanel } from "@/components/TopMetricsPanel";
import { StrategyBoard } from "@/components/StrategyBoard";
import { getLiveBacktest } from "@/lib/api";
import { strategies as dummyStrategies, summary, weeklyPnl } from "@/lib/dummy-data";

export default async function Home() {
  const live = await getLiveBacktest();

  const chartTitle = live ? "Equity semanal · EMA Crossover BTC" : "PnL semanal";
  const chartData = live
    ? live.equityCurve.slice(-5).map((point) => ({
        label: new Date(point.timestamp).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" }),
        value: point.equity,
      }))
    : weeklyPnl;

  const winRatePct = live ? live.metrics.win_rate * 100 : summary.winRatePct;
  const capitalActual = live ? (live.equityCurve.at(-1)?.equity ?? summary.capitalActual) : summary.capitalActual;
  const statLabel = live ? "Operaciones cerradas" : "Operaciones abiertas";
  const statValue = live ? String(live.numTrades) : String(summary.operacionesAbiertas);

  const strategies = dummyStrategies.map((strategy) =>
    live && strategy.id === "1"
      ? {
          ...strategy,
          profitFactor: live.metrics.profit_factor,
          maxDrawdownPct: live.metrics.max_drawdown * 100,
        }
      : strategy,
  );

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
          <p className="text-sm text-muted">Vista general de tu operativa</p>
        </div>
        <DataBadge live={false} label="Estrategias de ejemplo" />
      </div>

      <TopMetricsPanel
        chartTitle={chartTitle}
        chartData={chartData}
        winRatePct={winRatePct}
        capitalActual={capitalActual}
        statLabel={statLabel}
        statValue={statValue}
        live={live !== null}
      />

      <StrategyBoard strategies={strategies} />
    </div>
  );
}
