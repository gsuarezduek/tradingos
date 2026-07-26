import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { ConstructorClient, type ConditionCategory, type DatasetOption, type SavedStrategySummary } from "./ConstructorClient";

async function fetchStrategies(): Promise<{ strategies: SavedStrategySummary[]; error: string | null }> {
  const token = await getSessionToken();
  if (!token) return { strategies: [], error: "no autenticado" };

  try {
    const response = await fetch(`${API_BASE_URL}/strategies`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store", // datos por usuario: nunca compartir esta respuesta entre requests
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        strategies: [],
        error: typeof data.detail === "string" ? data.detail : "No se pudieron cargar tus estrategias.",
      };
    }
    return { strategies: data, error: null };
  } catch {
    return { strategies: [], error: "No se pudo conectar con la API." };
  }
}

// Datasets realmente disponibles en el servidor; público, sin auth (igual que /backtests/demo).
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

// Lista de símbolos de Binance para el autocomplete de mercados; mismo endpoint que ya
// usa Paper Trading. Si falla, el formulario sigue funcionando solo con los símbolos
// que ya tienen dataset (no bloqueamos la creación de estrategias por esto).
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

// Catálogo completo del constructor de condiciones (EMA disponible, el resto marcado
// "Próximamente"). Público, sin auth.
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

export default async function ConstructorPage() {
  const [{ strategies, error }, datasets, symbols, conditionCatalog] = await Promise.all([
    fetchStrategies(),
    fetchDatasets(),
    fetchSymbols(),
    fetchConditionCatalog(),
  ]);
  return (
    <ConstructorClient
      initialStrategies={strategies}
      initialError={error}
      datasets={datasets}
      symbols={symbols}
      conditionCatalog={conditionCatalog}
    />
  );
}
