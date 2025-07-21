# backtest.py

# Generic Backtesting Class
class Backtester:
    def __init__(self, timestamps, bids, asks, initial_cash=1):
        self.ts, self.bid, self.ask = timestamps, bids, asks
        self.cash = initial_cash
        self.shares = 0

        self.actions = []  # ("buy"/"sell", ts, price, qty)
        self.positions = []
        self.cash_history = []

    def buy(self, ts, price, qty):
        cost = price * qty
        if self.cash >= cost:
            self.cash -= cost
            self.shares += qty
            self.actions.append(("buy", ts, price, qty))

    def sell(self, ts, price, qty):
        if self.shares >= qty:
            self.cash += price * qty
            self.shares -= qty
            self.actions.append(("sell", ts, price, qty))

    def record_state(self):
        self.positions.append(self.shares)
        self.cash_history.append(self.cash)

    def run(self):
        raise NotImplementedError("Strategy logic must be implemented in subclass")