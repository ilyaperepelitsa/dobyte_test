#  alpha.py

from typing import Sequence
from .backtest import Strategy

__all__ = [
    "FutureLookupStrategy",  # default offset‑based strategy
    "NthValueStrategy",      # explicit subclass example
]


class FutureLookupStrategy(Strategy):
    """One‑step look‑ahead: always peeks **exactly** the next bar.

    No arguments needed – this is the simplest oracle.  More flexible
    variants should subclass and override ``future_lookup`` or change
    ``self.offset``.
    """

    def __init__(self):
        # hard‑coded to 1‑bar look‑ahead
        self.offset: int = 1

    # ---------------------------------------------------------------
    # ••• Hook method •••
    # ---------------------------------------------------------------
    def future_lookup(self, i: int, bid: Sequence[float], ask: Sequence[float]) -> tuple[float, float]:
        future_idx = min(i + self.offset, len(bid) - 1)
        return bid[future_idx], ask[future_idx]

    # ---------------------------------------------------------------
    def decide(
        self,
        i: int,
        ts: Sequence,
        bid: Sequence[float],
        ask: Sequence[float],
        cash: float,
        shares: int,
    ) -> str:
        fut_bid, fut_ask = self.future_lookup(i, bid, ask)
        if fut_bid > ask[i] and cash >= ask[i]:
            return "buy"
        if shares and fut_ask < bid[i]:
            return "sell"
        return "hold"


class NthValueStrategy(FutureLookupStrategy):
    """Look *exactly* ``offset`` bars ahead by overriding ``future_lookup``."""

    def __init__(self, offset: int = 5):
        super().__init__()
        self.offset = offset

    # ---------------------------------------------------------------
    def future_lookup(self, i: int, bid: Sequence[float], ask: Sequence[float]) -> tuple[float, float]:
        future_idx = min(i + self.offset, len(bid) - 1)
        return bid[future_idx], ask[future_idx]