import { Info } from "lucide-react";

// <details>/<summary> nativo: da el toggle con click sin necesitar useState ni
// "use client", así funciona igual dentro de Server Components y Client Components.
export function InfoGuide({ children }: { children: React.ReactNode }) {
  return (
    <details className="group relative inline-block align-middle">
      <summary
        className="flex h-5 w-5 cursor-pointer list-none items-center justify-center rounded-full border border-border text-muted marker:content-none hover:text-ink [&::-webkit-details-marker]:hidden"
        aria-label="Ver guía"
      >
        <Info size={12} />
      </summary>
      <div className="absolute left-0 top-full z-10 mt-2 w-72 rounded-xl border border-border bg-surface p-4 text-sm leading-relaxed text-muted shadow-lg">
        {children}
      </div>
    </details>
  );
}
