import ccxt
from config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE, TRADING_MODE

class TradeExecutor:
    def __init__(self, symbol):
        self.symbol = symbol
        if MODE == "live":
            if TRADING_MODE == "futures":
                self.exchange = ccxt.binanceusdm({
                    'apiKey': BINANCE_API_KEY,
                    'secret': BINANCE_API_SECRET,
                    'enableRateLimit': True,
                })
            else:
                self.exchange = ccxt.binance({
                    'apiKey': BINANCE_API_KEY,
                    'secret': BINANCE_API_SECRET,
                    'enableRateLimit': True,
                })
        self.position = None

    def place_order(self, side, amount, price=None):
        if MODE == "paper":
            print(f"[PAPER] {side.upper()} {amount:.6f} de {self.symbol}")
            return {"status": "filled", "price": price or 60000}
        else:
            if TRADING_MODE == "futures":
                # En futuros, usamos market order
                return self.exchange.create_market_order(self.symbol, side.upper(), amount)
            else:
                # Spot: solo buy/sell
                return self.exchange.create_market_order(self.symbol, side.upper(), amount)

    def close_position(self, amount, side="sell"):
        return self.place_order(side, amount)