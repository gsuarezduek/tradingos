import type { Percentiles } from "@/lib/api";

const ORDER: (keyof Percentiles)[] = ["p5", "p25", "p50", "p75", "p95"];

export function PercentileTable({
  title,
  values,
  format,
}: {
  title: string;
  values: Percentiles;
  format: (n: number) => string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <div className="mt-4 grid grid-cols-5 gap-2 text-center">
        {ORDER.map((key) => (
          <div key={key}>
            <div className="text-[10px] font-medium uppercase tracking-wide text-muted">{key}</div>
            <div className="mt-1 text-sm font-semibold text-ink">{format(values[key])}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
