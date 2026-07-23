import { DummyDataBadge } from "@/components/DummyDataBadge";
import { TopMetricsPanel } from "@/components/TopMetricsPanel";
import { StrategyBoard } from "@/components/StrategyBoard";

export default function Home() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
          <p className="text-sm text-muted">Vista general de tu operativa</p>
        </div>
        <DummyDataBadge />
      </div>

      <TopMetricsPanel />

      <StrategyBoard />
    </div>
  );
}
