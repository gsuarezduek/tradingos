import pytest

from tradingos.backtest.broker_sim import BrokerSimConfig, SimulatedBroker
from tradingos.core.types import Side


def test_latency_must_be_at_least_one():
    with pytest.raises(ValueError):
        BrokerSimConfig(latency_bars=0)


def test_entry_slippage_is_against_the_trader_for_long():
    broker = SimulatedBroker(BrokerSimConfig(slippage_pct=0.01, commission_pct=0.0, latency_bars=1))
    price = broker.fill_price(100.0, Side.LONG, is_entry=True)
    assert price == pytest.approx(101.0)  # comprar más caro


def test_exit_slippage_is_against_the_trader_for_long():
    broker = SimulatedBroker(BrokerSimConfig(slippage_pct=0.01, commission_pct=0.0, latency_bars=1))
    price = broker.fill_price(100.0, Side.LONG, is_entry=False)
    assert price == pytest.approx(99.0)  # vender más barato


def test_entry_slippage_is_against_the_trader_for_short():
    broker = SimulatedBroker(BrokerSimConfig(slippage_pct=0.01, commission_pct=0.0, latency_bars=1))
    price = broker.fill_price(100.0, Side.SHORT, is_entry=True)
    assert price == pytest.approx(99.0)  # vender en corto más barato


def test_commission_is_proportional():
    broker = SimulatedBroker(BrokerSimConfig(commission_pct=0.001))
    assert broker.commission(price=100.0, quantity=2.0) == pytest.approx(0.2)
