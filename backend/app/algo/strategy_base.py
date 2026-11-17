"""
Trading Strategy Base Class & Execution Runner.
Provides base interface for developing quantitative algorithms (Paper/Live/Backtest).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import structlog
from app.models.algo import SignalType

log = structlog.get_logger()

class BaseStrategy(ABC):
    def __init__(self, name: str, symbols: List[str], config: Dict[str, Any]):
        self.name = name
        self.symbols = symbols
        self.config = config

    @abstractmethod
    def on_tick(self, tick_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate live market tick or historical bar.
        Returns list of generated signals:
        [{ 'symbol': ..., 'signal_type': SignalType.BUY, 'price': ..., 'quantity': ..., 'confidence': ... }]
        """
        pass

    @abstractmethod
    def on_order_fill(self, fill_event: Dict[str, Any]) -> None:
        """Callback when an executed trade fill confirms."""
        pass

class MovingAverageCrossover(BaseStrategy):
    """
    Standard fast/slow EMA crossover strategy implementation.
    """
    def __init__(self, symbols: List[str], config: Dict[str, Any]):
        super().__init__("EMA_Crossover", symbols, config)
        self.fast_period = config.get("fast_period", 9)
        self.slow_period = config.get("slow_period", 21)
        self.price_history: Dict[str, List[float]] = {s: [] for s in symbols}

    def on_tick(self, tick_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        signals = []
        symbol = tick_data.get("symbol")
        ltp = tick_data.get("ltp")
        if not symbol or not ltp or symbol not in self.price_history:
            return signals

        history = self.price_history[symbol]
        history.append(ltp)
        if len(history) > 100:
            history.pop(0)

        if len(history) >= self.slow_period:
            fast_ema = sum(history[-self.fast_period:]) / self.fast_period
            slow_ema = sum(history[-self.slow_period:]) / self.slow_period

            if fast_ema > slow_ema and history[-2] <= slow_ema:
                signals.append({
                    "symbol": symbol,
                    "signal_type": SignalType.BUY,
                    "price": ltp,
                    "quantity": self.config.get("default_qty", 50),
                    "confidence": 0.82,
                    "notes": f"Fast EMA ({fast_ema:.2f}) crossed above Slow EMA ({slow_ema:.2f})"
                })
            elif fast_ema < slow_ema and history[-2] >= slow_ema:
                signals.append({
                    "symbol": symbol,
                    "signal_type": SignalType.SELL,
                    "price": ltp,
                    "quantity": self.config.get("default_qty", 50),
                    "confidence": 0.79,
                    "notes": f"Fast EMA ({fast_ema:.2f}) crossed below Slow EMA ({slow_ema:.2f})"
                })

        return signals

    def on_order_fill(self, fill_event: Dict[str, Any]) -> None:
        log.info("ema_crossover_order_fill", strategy=self.name, fill=fill_event)
