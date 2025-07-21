# alpha.py

from backtest import Backtester

# Base class for strategies involving future price lookups
class FutureLookupStrategy(Backtester):
    def future_lookup(self, i):
        # Default implementation: look at the immediate next value
        future_index = min(i + 1, len(self.bid) - 1)
        return self.bid[future_index], self.ask[future_index]

    def run(self):
        n = len(self.bid)

        for i in range(n - 1):
            t = self.ts[i]
            current_bid = self.bid[i]
            current_ask = self.ask[i]

            future_bid, future_ask = self.future_lookup(i)

            # Buy condition: Anticipate higher future bid price
            if future_bid > current_ask:
                qty = self.cash // current_ask
                if qty:
                    self.buy(t, current_ask, qty)

            # Sell condition: Anticipate lower future ask price
            elif future_ask < current_bid and self.shares:
                self.sell(t, current_bid, self.shares)

            self.record_state()

        return self.cash
