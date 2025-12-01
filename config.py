import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

SYMBOL = "BTC/USDT"
#TIMEFRAME = "1h"
INITIAL_CAPITAL = 1000.0
RISK_PER_TRADE = 0.01
MODE = "live"          # "paper" o "live"
TRADING_MODE = "futures"  # "spot" o "futures"
OPTIMIZE_EVERY = 10
SIGNAL_TIMEFRAME = "1h"    # Para generar señales
EXECUTION_TIMEFRAME = "5m" # Para ejecutar órdenes
LEVERAGE = 3  # Apalancamiento máximo deseado (3x)
UPDATE_CAPITAL_AFTER_EACH_TRADE = True
UPDATE_CAPITAL_EVERY_SECONDS = 30  # Frecuencia adicional de actualización6

RISK_REWARD_RATIO = 2.0  # Ratio riesgo/recompensa (1:2)
SL_BUFFER_MULTIPLIER = 1.5  # Holgura adicional para SL en mercados volátiles
MAX_LEVERAGE_DYNAMIC = 3  # Apalancamiento máximo dinámico
VOLATILITY_THRESHOLD = 0.02  # 2% de volatilidad para considerar mercado volátil