# select_strategy.py
from config import SYMBOL, TRADING_MODE
from strategy_selector import select_best_strategy

symbol_to_use = "BTC/USDT:USDT" if TRADING_MODE == "futures" else SYMBOL
select_best_strategy(symbol=symbol_to_use, days=30)