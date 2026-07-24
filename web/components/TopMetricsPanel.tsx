import { ArrowUpRight } from "lucide-react";
import { DataBadge } from "@/components/DataBadge";

interface ChartPoint {
  label: string;
  value: number;
}

function BarChart({ title, data }: { title: string; data: ChartPoint[] }) {
  const max = Math.max(...data.map((d) => d.value));
  return (
    <div>
      <div className="text-sm font-semibold text-ink">{title}</div>
      <div className="mt-4 flex h-32 gap-3">
        {data.map((d) => (
          <div key={d.label} className="flex flex-1 flex-col items-center gap-2">
            <div className="flex h-24 w-full items-end">
              <div
                className="w-full rounded-t-md bg-ink"
                style={{ height: `${(d.value / max) * 100}%` }}
              />
            </div>
            <span className="text-xs text-muted">{d.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RadialGauge({ percent, label }: { percent: number; label: string }) {
  const radius = 80;
  const circumference = Math.PI * radius;
  const filled = (Math.max(0, Math.min(100, percent)) / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 110" className="w-48">
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="var(--border)"
          strokeWidth={14}
          strokeLinecap="round"
        />
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="var(--ink)"
          strokeWidth={14}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
        <text
          x="100"
          y="90"
          textAnchor="middle"
          className="fill-ink text-3xl font-bold"
        >
          {Math.round(percent)}%
        </text>
      </svg>
      <span className="-mt-2 text-sm text-muted">{label}</span>
    </div>
  );
}

function StatBlock({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col justify-between">
      <div className="flex items-center gap-2">
        <span className="text-3xl font-bold text-ink">{value}</span>
      </div>
      <div className="mt-2 flex items-center gap-1 text-sm text-muted">
        {label}
        <ArrowUpRight size={14} />
      </div>
    </div>
  );
}

interface TopMetricsPanelProps {
  chartTitle: string;
  chartData: ChartPoint[];
  winRatePct: number;
  capitalActual: number;
  statLabel: string;
  statValue: string;
  live: boolean;
}

export function TopMetricsPanel({
  chartTitle,
  chartData,
  winRatePct,
  capitalActual,
  statLabel,
  statValue,
  live,
}: TopMetricsPanelProps) {
  return (
    <div className="relative rounded-3xl bg-panel p-8">
      <div className="absolute right-8 top-8">
        <DataBadge live={live} />
      </div>
      <div className="grid grid-cols-1 gap-8 md:grid-cols-[1.4fr_1fr_0.8fr_0.8fr] md:items-center">
        <BarChart title={chartTitle} data={chartData} />
        <RadialGauge percent={winRatePct} label="Win rate" />
        <StatBlock value={`$${capitalActual.toLocaleString("es-AR")}`} label="Capital actual" />
        <StatBlock value={statValue} label={statLabel} />
      </div>
    </div>
  );
}
