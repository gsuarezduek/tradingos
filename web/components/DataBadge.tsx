export function DataBadge({ live = false, label }: { live?: boolean; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] font-medium text-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-emerald-500" : "bg-amber-500"}`} />
      {label ?? (live ? "Backtest real" : "Datos de ejemplo")}
    </span>
  );
}
