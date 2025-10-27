# learner.py
from skopt import gp_minimize
from skopt.space import Real
import numpy as np
import pandas as pd
import pickle
from pathlib import Path
from data import fetch_ohlcv
from indicators import add_indicators
from strategy import should_enter_long, should_enter_short, should_exit_position
from risk_manager import calculate_position_size

# Parámetros por defecto
DEFAULT_PARAMS = {
    'rsi_upper': 60,
    'rsi_lower': 40,
    'wick_ratio': 2.0,
    'atr_multiple': 1.5,
    'risk_per_trade': 0.01
}

class BacktestOptimizer:
    def __init__(self, df, symbol, trading_mode="futures"):
        self.df = df
        self.symbol = symbol
        self.trading_mode = trading_mode

    def run_backtest_with_params(self, params):
        rsi_upper, rsi_lower, wick_ratio, atr_multiple, risk_per_trade = params
        
        # Simular backtest con estos parámetros
        capital = 1000.0
        position = None
        trades = 0
        total_pnl = 0.0

        for i in range(200, len(self.df)):
            current_df = self.df.iloc[:i+1].copy()
            current_df = add_indicators(current_df)
            current_price = current_df['close'].iloc[-1]

            # Cerrar posición
            if position:
                sl_hit, tp_hit, sl, tp = should_exit_position(
                    current_df, position['entry'], position['type'], atr_multiple
                )
                if sl_hit or tp_hit:
                    pnl = (current_price - position['entry']) * position['size']
                    if position['type'] == 'short':
                        pnl = -pnl
                    total_pnl += pnl
                    capital += pnl
                    position = None
                    trades += 1

            # Abrir posición
            if position is None:
                # Temporalmente inyectamos los parámetros en la estrategia
                # (en producción, pasarías params a las funciones)
                last = current_df.iloc[-1]
                if (last['close'] > last['ema50'] > last['ema200'] and
                    last['rsi'] < rsi_upper and
                    last['lower_wick'] > wick_ratio * last['body']):
                    # LONG
                    sl = current_price - last['atr'] * atr_multiple
                    size = calculate_position_size(capital, current_price, sl, risk_per_trade)
                    if size > 0:
                        position = {'type': 'long', 'size': size, 'entry': current_price}
                elif (self.trading_mode == "futures" and
                      last['close'] < last['ema50'] < last['ema200'] and
                      last['rsi'] > rsi_lower and
                      last['upper_wick'] > wick_ratio * last['body']):
                    # SHORT
                    sl = current_price + last['atr'] * atr_multiple
                    size = calculate_position_size(capital, current_price, sl, risk_per_trade)
                    if size > 0:
                        position = {'type': 'short', 'size': size, 'entry': current_price}

        # Métrica a optimizar: Sharpe ratio aproximado (PnL / sqrt(trades))
        if trades == 0:
            return -1e-6  # penalizar no operar
        sharpe = total_pnl / np.sqrt(trades)
        return -sharpe  # minimizar negativo = maximizar Sharpe

def optimize_parameters(symbol="BTC/USDT:USDT", trading_mode="futures", days=2):
    print("🧠 Iniciando optimización con datos reales...")
    
    # Cargar datos históricos
    limit = 1440 * days  # minutos en 'days' días
    df = fetch_ohlcv(symbol, "1m", limit=limit)
    if df.empty or len(df) < 300:
        print("⚠️  Datos insuficientes para optimizar.")
        return DEFAULT_PARAMS

    optimizer = BacktestOptimizer(df, symbol, trading_mode)
    
    # Espacio de búsqueda
    space = [
        Real(50, 70, name='rsi_upper'),
        Real(30, 50, name='rsi_lower'),
        Real(1.5, 3.0, name='wick_ratio'),
        Real(1.0, 2.5, name='atr_multiple'),
        Real(0.005, 0.02, name='risk_per_trade')
    ]

    # Optimizar
    result = gp_minimize(
        optimizer.run_backtest_with_params,
        space,
        n_calls=40,
        random_state=42,
        n_jobs=-1
    )

    best = dict(zip(['rsi_upper', 'rsi_lower', 'wick_ratio', 'atr_multiple', 'risk_per_trade'], result.x))
    
    # Guardar
    with open('best_params.pkl', 'wb') as f:
        pickle.dump(best, f)
    
    print(f"✅ Nuevos parámetros guardados: {best}")
    return best

def load_best_params():
    try:
        with open('best_params.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return DEFAULT_PARAMS