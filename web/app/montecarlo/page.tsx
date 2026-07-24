import { DataBadge } from "@/components/DataBadge";
import { InfoGuide } from "@/components/InfoGuide";
import { PercentileTable } from "@/components/PercentileTable";
import { getLiveMonteCarlo } from "@/lib/api";

function formatCurrency(n: number) {
  return `$${Math.round(n).toLocaleString("es-AR")}`;
}

function formatPct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

export default async function MonteCarloPage() {
  const mc = await getLiveMonteCarlo();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-ink">
            Simulación Monte Carlo
            <InfoGuide>
              Toma los trades de un backtest real y los resamplea miles de veces en distinto orden para
              estimar qué tan sensible es el resultado a la secuencia exacta en que ocurrieron las operaciones.
              La &quot;probabilidad de profit&quot; y los percentiles de equity/drawdown muestran un rango de
              resultados posibles, no una predicción — compará contra el profit factor y drawdown del backtest
              real para juzgar qué tan robusto es.
            </InfoGuide>
          </h1>
          <p className="text-sm text-muted">Robustez del resultado de EMA Crossover BTC</p>
        </div>
        <DataBadge live={mc !== null} label={mc ? "Simulación real" : "No disponible"} />
      </div>

      {!mc && (
        <div className="rounded-3xl bg-panel p-8 text-center text-sm text-muted">
          No se pudo cargar la simulación Monte Carlo. Probá de nuevo en unos minutos.
        </div>
      )}

      {mc && (
        <>
          <div className="rounded-3xl bg-panel p-8">
            <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
              <div>
                <span className="text-3xl font-bold text-ink">{formatPct(mc.probabilityOfProfit)}</span>
                <p className="mt-2 text-sm text-muted">Probabilidad de profit ({mc.numSimulations} simulaciones)</p>
              </div>
              <div>
                <span className="text-3xl font-bold text-ink">{mc.originalMetrics.profit_factor.toFixed(3)}</span>
                <p className="mt-2 text-sm text-muted">Profit factor del backtest real</p>
              </div>
              <div>
                <span className="text-3xl font-bold text-ink">{formatPct(mc.originalMetrics.max_drawdown)}</span>
                <p className="mt-2 text-sm text-muted">Max drawdown del backtest real</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <PercentileTable title="Equity final" values={mc.finalEquityPercentiles} format={formatCurrency} />
            <PercentileTable title="Max drawdown" values={mc.maxDrawdownPercentiles} format={formatPct} />
          </div>
        </>
      )}
    </div>
  );
}
