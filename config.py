import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "1h"
INITIAL_CAPITAL = 1000.0
RISK_PER_TRADE = 0.01
MODE = "paper"          # "paper" o "live"
TRADING_MODE = "futures"  # "spot" o "futures"
OPTIMIZE_EVERY = 10