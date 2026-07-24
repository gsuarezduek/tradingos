import { DataBadge } from "@/components/DataBadge";
import { getLiveOptimization } from "@/lib/api";

export default async function OptimizadorPage() {
  const optimization = await getLiveOptimization();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Optimizador</h1>
          <p className="text-sm text-muted">Grid search sobre EMA Crossover BTC</p>
        </div>
        <DataBadge live={optimization !== null} label={optimization ? "Grid search real" : "No disponible"} />
      </div>

      {!optimization && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          No se pudo cargar el resultado del optimizador. Probá de nuevo en unos minutos.
        </div>
      )}

      {optimization && (
        <div className="rounded-3xl bg-panel p-8">
          <p className="text-sm text-muted">
            {optimization.totalCombinations} combinaciones evaluadas, ordenadas por profit factor.
          </p>
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="pb-3 pr-4 font-medium">#</th>
                  <th className="pb-3 pr-4 font-medium">EMA rápida</th>
                  <th className="pb-3 pr-4 font-medium">Stop Loss %</th>
                  <th className="pb-3 pr-4 font-medium">Profit Factor</th>
                  <th className="pb-3 pr-4 font-medium">Max Drawdown %</th>
                  <th className="pb-3 font-medium">Trades</th>
                </tr>
              </thead>
              <tbody>
                {optimization.results.map((row, i) => (
                  <tr
                    key={i}
                    className={`border-b border-border last:border-0 ${i === 0 ? "bg-surface" : ""}`}
                  >
                    <td className="py-3 pr-4 text-muted">{i + 1}</td>
                    <td className="py-3 pr-4 text-ink">{row.emaFastPeriod}</td>
                    <td className="py-3 pr-4 text-ink">{(row.stopLossPct * 100).toFixed(1)}%</td>
                    <td className="py-3 pr-4 font-semibold text-ink">{row.profitFactor.toFixed(3)}</td>
                    <td className="py-3 pr-4 text-ink">{row.maxDrawdownPct.toFixed(1)}%</td>
                    <td className="py-3 text-ink">{row.numTrades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
