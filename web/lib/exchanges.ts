export interface ExchangeOption {
  value: string;
  label: string;
  requiresPassphrase: boolean;
}

// Fuente única entre server (fetch inicial de conexiones) y client (formulario /
// listado). Agregar un exchange acá alcanza para que aparezca en el selector y en el
// merge de conexiones — la lógica de balances/creación ya es genérica sobre `value`.
export const EXCHANGES: ExchangeOption[] = [
  { value: "binance", label: "Binance", requiresPassphrase: false },
  { value: "mexc", label: "MEXC", requiresPassphrase: false },
  { value: "bitget", label: "Bitget", requiresPassphrase: true },
  { value: "bingx", label: "BingX", requiresPassphrase: false },
];
