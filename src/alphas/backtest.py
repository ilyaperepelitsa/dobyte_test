# backtest.py
"""Core event‑driven back‑testing engine (single asset).

* 3 actions: **buy / sell / hold**.
* Pluggable Strategy interface (see below).
* Built‑in metric computation – **both** program‑friendly short names *and* human
  descriptions via a configurable *stat_name_map*.

Example
-------
```python
from alphas.future_lookup import FutureLookupStrategy
from utils.loader import load_data

stat_map = {
    "ann_ret": "Annualized return (linear)",
    "ann_turnover_bil": "Annualized turnover (billion times)",
    # ... you can extend / override
}

TS, BIDS, ASKS = load_data()
engine = Backtester(TS, BIDS, ASKS, FutureLookupStrategy(offset=5), stat_name_map=stat_map)
engine.run()
print(engine.stats("prog"))   # short keys
print(engine.stats("desc"))   # verbose keys
```
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence, List, Tuple, Dict
import math
import json
import csv

import numpy as np
import pandas as pd

# use *existing* performance helpers – do NOT redeclare
from .performance import (
    annualized_returns_linear,
    annualized_turnover,
    max_drawdown,
    hit_rate,
    long_only_hitrate,
    naive_portfolio_efficiency,
    annualized_sharpe,
    sortino_ratio,
    calmar_ratio,
    compute_effective_period_count,
    estimate_annualization_factor_unix
)

__all__ = ["Strategy", "Backtester"]


# --------------------------------------------------------------------
# Strategy protocol (remains intentionally minimal!)
# --------------------------------------------------------------------
class Strategy(ABC):
    """Abstract interface for trading logic.

    The back‑tester calls ``decide`` for **every** index *i* in the price
    stream. Return exactly one of *"buy"*, *"sell"*, or *"hold"*.
    """

    @abstractmethod
    def decide(
        self,
        i: int,
        ts: Sequence,
        bid: Sequence[float],
        ask: Sequence[float],
        cash: float,
        shares: int,
    ) -> str:  # 'buy' | 'sell' | 'hold'
        """Return trading decision for bar *i*."""


# --------------------------------------------------------------------
# Execution engine
# --------------------------------------------------------------------
class Backtester:
    """Runs a *Strategy* in a single pass and computes rich statistics."""

    DEFAULT_STAT_MAP: Dict[str, str] = {
        "ann_ret": "Annualized return (linear)",
        "ann_turnover_bil": "Annualized turnover (billion times)",
        "max_drawdown": "Max drawdown",
        "hitrate": "Hit rate",
        "efficiency": "Portfolio efficiency",
        "ann_sharpe": "Annualized Sharpe",
        "sortino": "Sortino ratio",
        "calmar": "Calmar ratio",
    }

    # ----------------------------------------------------------------
    def __init__(
        self,
        timestamps: Sequence,
        bids: Sequence[float],
        asks: Sequence[float],
        strategy: Strategy,
        *,
        initial_cash: float = 1.0,
        stat_name_map: Dict[str, str] | None = None,
    ) -> None:
        if not (len(timestamps) == len(bids) == len(asks)):
            raise ValueError("timestamps, bids and asks must be same length")

        self.ts, self.bid, self.ask = list(timestamps), list(bids), list(asks)
        self.strategy = strategy
        self.cash: float = initial_cash
        self.shares: int = 0

        # history
        self._trades: List[Tuple[str, object, float, int]] = []
        self._pos_hist: List[int] = []
        self._cash_hist: List[float] = []

        # mapping between programmatic keys and human names
        self.stat_name_map: Dict[str, str] = (stat_name_map or {}).copy()
        # merge with defaults but allow user overrides
        for k, v in self.DEFAULT_STAT_MAP.items():
            self.stat_name_map.setdefault(k, v)
        # derive reverse mapping for fast lookup
        self._desc_to_prog = {v: k for k, v in self.stat_name_map.items()}

    # ----------------------------------------------------------------
    # internal helpers
    # ----------------------------------------------------------------
    def _execute(self, side: str, i: int):
        price = self.ask[i] if side == "buy" else self.bid[i]
        qty = math.floor(self.cash / price) if side == "buy" else self.shares
        if qty == 0:
            return
        if side == "buy":
            self.cash -= qty * price
            self.shares += qty
        else:
            self.cash += qty * price
            self.shares -= qty
        self._trades.append((side, self.ts[i], price, qty))

    def _mark(self):
        self._pos_hist.append(self.shares)
        self._cash_hist.append(self.cash)

    # ----------------------------------------------------------------
    # public API
    # ----------------------------------------------------------------
    def run(self) -> float:
        n = len(self.bid)
        for i in range(n - 1):
            action = self.strategy.decide(i, self.ts, self.bid, self.ask, self.cash, self.shares)
            if action in ("buy", "sell"):
                self._execute(action, i)
            self._mark()
        # final liquidation
        if self.shares:
            self.cash += self.shares * self.bid[-1]
            self._trades.append(("final_liq", self.ts[-1], self.bid[-1], self.shares))
            self.shares = 0
        self._mark()
        return self.cash

    # ----------------------------- analytics ------------------------
    def _compute_metrics(self) -> Dict[str, float]:
        curve = self.equity_curve()
        rets = curve.pct_change()
        wts = self.weights()
        total_periods = compute_effective_period_count(self.ts, target_period_length="1s")
        ann_factor = estimate_annualization_factor_unix(self.ts)
        return {
            "Annualized return (linear)": annualized_returns_linear(rets.add(1).prod() - 1, total_periods, ann_factor),
            "Annualized turnover (billion times)": annualized_turnover(np.nansum(np.abs(wts)), total_periods, freq=None, annualization_factor=ann_factor) / 1e9,
            "Max drawdown": max_drawdown(rets.fillna(0.0)),
            "Hit rate": long_only_hitrate(rets),
            "Portfolio efficiency": naive_portfolio_efficiency(rets, wts, timestamps=self.ts),
            "Annualized Sharpe": annualized_sharpe(rets, annualization_factor=ann_factor),
            "Sortino ratio": sortino_ratio(rets.fillna(0.0), annualization_factor=ann_factor),
            "Calmar ratio": calmar_ratio(rets.fillna(0.0), annualization_factor=ann_factor, timestamps=self.ts),
        }

    def stats(self, style: str = "desc") -> Dict[str, float] | Dict[str, Dict[str, float]]:
        """Return metrics in *style*:

        * ``"desc"`` – descriptive keys (default)
        * ``"prog"`` – programmatic short keys
        * ``"both"`` – {"prog": <dict>, "desc": <dict>} wrapper
        """
        desc_dict = {k: float(v) for k, v in self._compute_metrics().items()}
        prog_dict = {self._desc_to_prog[k]: v for k, v in desc_dict.items() if k in self._desc_to_prog}

        if style == "desc":
            return desc_dict
        if style == "prog":
            return prog_dict
        if style == "both":
            return {"prog": prog_dict, "desc": desc_dict}
        raise ValueError("style must be 'desc', 'prog', or 'both'")

    # ----------------------------- util series ----------------------
    def equity_curve(self) -> pd.Series:
        mtm = [p * px + c for p, px, c in zip(self._pos_hist, self.bid[: len(self._pos_hist)], self._cash_hist)]
        return pd.Series(mtm, index=pd.to_datetime(self.ts[: len(mtm)]))

    def weights(self) -> pd.Series:
        w = [((p * px) / (p * px + c)) if (p * px + c) else np.nan for p, px, c in zip(self._pos_hist, self.bid[: len(self._pos_hist)], self._cash_hist)]
        return pd.Series(w, index=pd.to_datetime(self.ts[: len(w)]))

    # ----------------------------- persistence ----------------------
    def save_results(self, path: str | Path, stats_style: str = "both"):
        """Persist trades + metrics (JSON/CSV).``stats_style`` passed to ``stats``."""
        path = Path(path)
        data = {
            "trades": self._trades,
            "equity_curve": self.equity_curve().tolist(),
            "weights": self.weights().tolist(),
            "stats": self.stats(stats_style),
        }
        if path.suffix == ".json":
            path.write_text(json.dumps(data, indent=2, default=str))
        else:
            self._save_csv(path)

    def _save_csv(self, path: Path):
        with path.open("w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["side", "timestamp", "price", "quantity"])
            wr.writerows(self._trades)

    # ----------------------------- accessors ------------------------
    @property
    def positions(self):
        return self._pos_hist

    @property
    def cash_history(self):
        return self._cash_hist

    @property
    def trades(self):
        return self._trades

