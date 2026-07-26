import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import type { ConditionCategory, DatasetOption } from "../EstrategiasClient";
import { StrategyDetailClient, type StrategyDetail } from "./StrategyDetailClient";

async function fetchStrategy(id: string): Promise<{ strategy: StrategyDetail | null; error: string | null }> {
  const token = await getSessionToken();
  if (!token) return { strategy: null, error: "no autenticado" };

  try {
    const response = await fetch(`${API_BASE_URL}/strategies/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store", // datos por usuario: nunca compartir esta respuesta entre requests
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        strategy: null,
        error: typeof data.detail === "string" ? data.detail : "No se pudo cargar la estrategia.",
      };
    }
    return { strategy: data, error: null };
  } catch {
    return { strategy: null, error: "No se pudo conectar con la API." };
  }
}

async function fetchDatasets(): Promise<DatasetOption[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategies/datasets`, {
      signal: AbortSignal.timeout(10000),
      next: { revalidate: 300 },
    });
    if (!response.ok) return [];
    return await response.json();
  } catch {
    return [];
  }
}

async function fetchConditionCatalog(): Promise<ConditionCategory[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategies/conditions/catalog`, {
      signal: AbortSignal.timeout(10000),
      next: { revalidate: 300 },
    });
    if (!response.ok) return [];
    return await response.json();
  } catch {
    return [];
  }
}

// Lista de símbolos de Binance para el autocomplete de mercados al editar; mismo
// endpoint que usa la página principal de Estrategias y Paper Trading.
async function fetchSymbols(): Promise<string[]> {
  const token = await getSessionToken();
  if (!token) return [];

  try {
    const response = await fetch(`${API_BASE_URL}/paper-trading/symbols`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(15000),
      cache: "no-store",
    });
    if (!response.ok) return [];
    return await response.json();
  } catch {
    return [];
  }
}

export default async function StrategyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [{ strategy, error }, datasets, conditionCatalog, symbols] = await Promise.all([
    fetchStrategy(id),
    fetchDatasets(),
    fetchConditionCatalog(),
    fetchSymbols(),
  ]);
  return (
    <StrategyDetailClient
      strategyId={id}
      initialStrategy={strategy}
      initialError={error}
      datasets={datasets}
      conditionCatalog={conditionCatalog}
      symbols={symbols}
    />
  );
}
