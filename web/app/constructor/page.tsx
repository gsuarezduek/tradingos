import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { ConstructorClient, type DatasetOption, type SavedStrategySummary } from "./ConstructorClient";

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

// Catálogo de estrategias registradas (ej. "ma_crossover") y datasets realmente
// disponibles en el servidor; ambos son públicos, sin auth (igual que /backtests/demo).
async function fetchCatalog(): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategies/catalog`, {
      signal: AbortSignal.timeout(10000),
      next: { revalidate: 300 },
    });
    if (!response.ok) return [];
    return await response.json();
  } catch {
    return [];
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

export default async function ConstructorPage() {
  const [{ strategies, error }, catalog, datasets] = await Promise.all([
    fetchStrategies(),
    fetchCatalog(),
    fetchDatasets(),
  ]);
  return (
    <ConstructorClient initialStrategies={strategies} initialError={error} catalog={catalog} datasets={datasets} />
  );
}
