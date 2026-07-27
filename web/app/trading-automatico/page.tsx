import { API_BASE_URL } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import { EXCHANGES } from "@/lib/exchanges";
import type { SavedStrategySummary } from "@/app/estrategias/EstrategiasClient";
import type { Connection } from "@/app/operar/OperarClient";
import { TradingAutomaticoClient, type LiveSessionSummary, type RiskSettings } from "./TradingAutomaticoClient";

async function fetchSessions(token: string): Promise<{ sessions: LiveSessionSummary[]; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE_URL}/live-trading/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        sessions: [],
        error: typeof data.detail === "string" ? data.detail : "No se pudieron cargar tus sesiones.",
      };
    }
    return { sessions: data, error: null };
  } catch {
    return { sessions: [], error: "No se pudo conectar con la API." };
  }
}

// Estrategias guardadas en Estrategias: igual que paper trading, trading en vivo
// siempre parte de una de estas, nunca de una config armada en esta pantalla.
async function fetchStrategies(token: string): Promise<{ strategies: SavedStrategySummary[]; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategies`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
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

// Única fuente de verdad para qué temporalidades se pueden activar acá: la calcula el
// backend (piso del cron de trading en vivo) en vez de reimplementarla en el cliente.
async function fetchLimits(token: string): Promise<{ eligibleTimeframes: string[]; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE_URL}/live-trading/limits`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        eligibleTimeframes: [],
        error: typeof data.detail === "string" ? data.detail : "No se pudieron cargar los límites.",
      };
    }
    return { eligibleTimeframes: data.eligible_timeframes, error: null };
  } catch {
    return { eligibleTimeframes: [], error: "No se pudo conectar con la API." };
  }
}

async function fetchRiskSettings(token: string): Promise<{ riskSettings: RiskSettings; error: string | null }> {
  const fallback: RiskSettings = {
    daily_loss_limit_usdt: null,
    weekly_loss_limit_usdt: null,
    max_exposure_per_asset_usdt: null,
    max_exposure_per_strategy_usdt: null,
  };
  try {
    const response = await fetch(`${API_BASE_URL}/live-trading/risk-settings`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        riskSettings: fallback,
        error: typeof data.detail === "string" ? data.detail : "No se pudieron cargar los límites de riesgo.",
      };
    }
    return { riskSettings: data, error: null };
  } catch {
    return { riskSettings: fallback, error: "No se pudo conectar con la API." };
  }
}

async function fetchConnections(token: string): Promise<{ connections: Connection[]; error: string | null }> {
  try {
    const responses = await Promise.all(
      EXCHANGES.map((exchange) =>
        fetch(`${API_BASE_URL}/brokers/${exchange.value}/connections`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(10000),
          cache: "no-store",
        }),
      ),
    );
    const bodies = await Promise.all(responses.map((r) => r.json()));
    const failedIndex = responses.findIndex((r) => !r.ok);
    if (failedIndex !== -1) {
      return {
        connections: [],
        error: typeof bodies[failedIndex].detail === "string" ? bodies[failedIndex].detail : "No se pudieron cargar tus conexiones.",
      };
    }
    const connections = (bodies as Connection[][]).flat();
    connections.sort((a, b) => a.created_at.localeCompare(b.created_at));
    return { connections, error: null };
  } catch {
    return { connections: [], error: "No se pudo conectar con la API." };
  }
}

export default async function TradingAutomaticoPage() {
  const token = await getSessionToken();
  if (!token) {
    return (
      <TradingAutomaticoClient
        initialSessions={[]}
        sessionsError="no autenticado"
        strategies={[]}
        strategiesError="no autenticado"
        connections={[]}
        connectionsError="no autenticado"
        eligibleTimeframes={[]}
        initialRiskSettings={{
          daily_loss_limit_usdt: null,
          weekly_loss_limit_usdt: null,
          max_exposure_per_asset_usdt: null,
          max_exposure_per_strategy_usdt: null,
        }}
      />
    );
  }

  const [
    { sessions, error: sessionsError },
    { strategies, error: strategiesError },
    { connections, error: connectionsError },
    { eligibleTimeframes },
    { riskSettings },
  ] = await Promise.all([
    fetchSessions(token),
    fetchStrategies(token),
    fetchConnections(token),
    fetchLimits(token),
    fetchRiskSettings(token),
  ]);

  return (
    <TradingAutomaticoClient
      initialSessions={sessions}
      sessionsError={sessionsError}
      strategies={strategies}
      strategiesError={strategiesError}
      connections={connections}
      connectionsError={connectionsError}
      eligibleTimeframes={eligibleTimeframes}
      initialRiskSettings={riskSettings}
    />
  );
}
