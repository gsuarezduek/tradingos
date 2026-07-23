from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tradingos.backtest.broker_sim import SimulatedBroker
from tradingos.backtest.metrics import compute_metrics
from tradingos.backtest.result import BacktestResult
from tradingos.core.risk import (
    exit_price_hit,
    initial_stop_loss,
    initial_take_profit,
    position_size,
    update_trailing_stop,
)
from tradingos.core.strategy import Strategy, StrategyContext
from tradingos.core.types import Position, Side, SignalAction, Trade

_TIMEFRAME_PERIODS_PER_YEAR = {
    "1m": 365 * 24 * 60,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
    "1h": 365 * 24,
    "4h": 365 * 6,
    "1d": 365,
}

_NON_INDICATOR_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


@dataclass(slots=True)
class _PendingSignal:
    execute_at: int
    action: SignalAction
    side: Side | None


class BacktestEngine:
    """Loop event-driven bar a bar.

    La estrategia solo decide *cuándo* entrar o salir (condiciones de entrada/salida);
    el SL/TP/trailing y el dimensionamiento por riesgo de StrategyConfig los aplica el
    motor de forma centralizada, para que ninguna estrategia tenga que reimplementarlos.
    """

    def __init__(self, strategy: Strategy, broker: SimulatedBroker | None = None, initial_equity: float = 10_000.0) -> None:
        self.strategy = strategy
        self.broker = broker or SimulatedBroker()
        self.initial_equity = initial_equity

    def run(self, data: pd.DataFrame) -> BacktestResult:
        prepared = self.strategy.prepare(data.copy()).reset_index(drop=True)
        indicator_cols = [c for c in prepared.columns if c not in _NON_INDICATOR_COLUMNS]
        first_valid_idx = prepared[indicator_cols].dropna().index.min() if indicator_cols else 0
        first_valid = 0 if pd.isna(first_valid_idx) else int(first_valid_idx)

        equity = self.initial_equity
        position: Position | None = None
        pending: _PendingSignal | None = None
        trades: list[Trade] = []
        timestamps: list[pd.Timestamp] = []
        equity_values: list[float] = []

        for i in range(first_valid, len(prepared)):
            row = prepared.iloc[i]

            # 1. órdenes protectoras (SL/TP/trailing) ya "apoyadas" en el broker: se
            #    revisan siempre, sin latencia, porque no son decisiones nuevas.
            if position is not None:
                update_trailing_stop(position, row["close"], self.strategy.config)
                exit_price = exit_price_hit(position, row["low"], row["high"])
                if exit_price is not None:
                    filled_price = self.broker.fill_price(exit_price, position.side, is_entry=False)
                    filled_price = min(max(filled_price, row["low"]), row["high"])
                    equity, position = self._close_position(position, filled_price, row["timestamp"], equity, trades)

            # 2. ejecutar una señal discrecional pendiente (entrada o salida), respetando latencia
            if pending is not None and pending.execute_at == i:
                if pending.action is SignalAction.OPEN and position is None:
                    equity, position = self._open_position(pending.side, row, equity)
                elif pending.action is SignalAction.CLOSE and position is not None:
                    exit_ref = self.broker.fill_price(row["open"], position.side, is_entry=False)
                    equity, position = self._close_position(position, exit_ref, row["timestamp"], equity, trades)
                pending = None

            # 3. preguntarle a la estrategia por una nueva señal (entrada o salida)
            if pending is None:
                context = StrategyContext(history=prepared, current_index=i, position=position, equity=equity)
                signal = self.strategy.on_bar(context)
                if signal is not None:
                    if signal.action is SignalAction.OPEN and position is None and signal.side is not None:
                        pending = _PendingSignal(execute_at=i + self.broker.config.latency_bars, action=signal.action, side=signal.side)
                    elif signal.action is SignalAction.CLOSE and position is not None:
                        pending = _PendingSignal(execute_at=i + self.broker.config.latency_bars, action=signal.action, side=None)

            # 4. marcar a mercado
            mark_to_market = equity + (position.unrealized_pnl(row["close"]) if position else 0.0)
            timestamps.append(row["timestamp"])
            equity_values.append(mark_to_market)

        equity_curve = pd.Series(equity_values, index=pd.DatetimeIndex(timestamps), name="equity")
        periods_per_year = _TIMEFRAME_PERIODS_PER_YEAR.get(self.strategy.config.timeframe, 365)
        metrics = compute_metrics(trades, equity_curve, periods_per_year)
        return BacktestResult(equity_curve=equity_curve, trades=trades, metrics=metrics)

    def _open_position(self, side: Side, row: pd.Series, equity: float) -> tuple[float, Position]:
        filled_price = self.broker.fill_price(row["open"], side, is_entry=True)
        stop = initial_stop_loss(filled_price, side, self.strategy.config)
        take_profit = initial_take_profit(filled_price, side, self.strategy.config)
        qty = position_size(equity, filled_price, stop if stop is not None else filled_price, self.strategy.config)
        commission = self.broker.commission(filled_price, qty)
        equity -= commission
        position = Position(
            side=side,
            entry_price=filled_price,
            quantity=qty,
            stop_loss=stop,
            take_profit=take_profit,
            entry_timestamp=row["timestamp"],
        )
        return equity, position

    def _close_position(
        self, position: Position, exit_price: float, exit_timestamp: pd.Timestamp, equity: float, trades: list[Trade]
    ) -> tuple[float, None]:
        commission = self.broker.commission(exit_price, position.quantity)
        trade = Trade(
            side=position.side,
            entry_timestamp=position.entry_timestamp,
            exit_timestamp=exit_timestamp,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            commission=commission,
        )
        equity += trade.pnl
        trades.append(trade)
        return equity, None
