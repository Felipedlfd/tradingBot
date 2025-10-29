# backtest_ml.py
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from config import SYMBOL, TRADING_MODE, INITIAL_CAPITAL
from data import fetch_ohlcv
from indicators import add_indicators
from risk_manager import calculate_position_size
from utils import save_trade

# Silenciar logs
logging.basicConfig(level=logging.WARNING)

try:
    import joblib
    MODEL = joblib.load('ml_model.pkl')
    FEATURE_COLS = joblib.load('feature_cols.pkl')
    ML_READY = True
except FileNotFoundError:
    print("❌ Modelo ML no encontrado. Ejecuta primero: python ml_trainer.py")
    ML_READY = False

class MLBacktester:
    def __init__(self, symbol, timeframe, capital):
        self.symbol = symbol
        self.timeframe = timeframe
        self.capital = capital
        self.initial_capital = capital
        self.position = None
        self.trades = []
        self.equity_curve = []

    def run_backtest(self, df):
        if not ML_READY:
            return
        
        print(f"📊 Backtest con ML en {self.timeframe} para {self.symbol}")
        print(f"📈 Velas: {len(df)} ({df.index[0]} → {df.index[-1]})\n")

        self.equity_curve.append((df.index[0], self.capital))

        for i in range(200, len(df)):
            current_df = df.iloc[:i+1].copy()
            current_df = add_indicators(current_df)
            
            # Asegurar liquidez si no está
            if 'liquidez' not in current_df.columns:
                current_df['spread'] = (current_df['high'] - current_df['low']) / current_df['close']
                current_df['liquidez'] = current_df['volume'] / (current_df['spread'] + 1e-8)
            
            current_price = current_df['close'].iloc[-1]
            current_time = df.index[i]

            # Cerrar posición (SL/TP simple)
            if self.position:
                sl_hit, tp_hit = self._check_exit(current_df, current_price)
                if sl_hit or tp_hit:
                    self._close_position(current_price, 'SL' if sl_hit else 'TP', current_time)

            self.equity_curve.append((current_time, self.capital))

            # Abrir posición con ML
            if self.position is None:
                signal = self._get_ml_signal(current_df)
                if signal == 'long':
                    self._open_position(current_df, 'long')
                elif signal == 'short' and TRADING_MODE == "futures":
                    self._open_position(current_df, 'short')

        self._print_summary()
        self._plot_equity_curve()

    def _get_ml_signal(self, df):
        try:
            last_row = df[FEATURE_COLS].iloc[-1:].copy()
            pred = MODEL.predict(last_row)[0]
            proba = MODEL.predict_proba(last_row)[0]
            confidence = max(proba)
            
            if confidence < 0.6:  # 0.6 para 1hr umbral mínimo
                return 'wait'
            return 'long' if pred == 1 else 'short' if pred == -1 else 'wait'
        except Exception as e:
            return 'wait'

    def _check_exit(self, df, current_price):
        if not self.position:
            return False, False
        
        atr = df['atr'].iloc[-1]
        # 👇 Ajusta para timeframe bajo
        sl_mult = 1.5  # en vez de 1.5
        tp_mult = 1.6  # ratio 1:2
        
        if self.position['type'] == 'long':
            sl = self.position['entry'] - atr * sl_mult
            tp = self.position['entry'] + atr * tp_mult
            return current_price <= sl, current_price >= tp
        else:
            sl = self.position['entry'] + atr * sl_mult
            tp = self.position['entry'] - atr * tp_mult
            return current_price >= sl, current_price <= tp

    def _open_position(self, df, pos_type):
        last = df.iloc[-1]
        entry_price = last['close']
        atr = last['atr']
        sl = entry_price - atr * 0.8 if pos_type == 'long' else entry_price + atr * 0.8
        size = calculate_position_size(self.capital, entry_price, sl, 0.01)
        if size <= 0:
            return

        self.position = {
            'type': pos_type,
            'size': size,
            'entry': entry_price,
            'sl': sl,
            'entry_time': df.index[-1]  # ← Fecha/hora de entrada
        }
        self.trades.append({
            'type': pos_type,
            'price': entry_price,
            'size': size,
            'timestamp': df.index[-1],  # ← Fecha/hora de entrada
            'strategy': 'ml_model'
        })
        print(f"🤖 {'LONG' if pos_type == 'long' else 'SHORT'} | "
            f"Entrada: {df.index[-1].strftime('%Y-%m-%d %H:%M')} a ${entry_price:.2f}")

    def _close_position(self, price, reason, timestamp):
        pnl = (price - self.position['entry']) * self.position['size']
        if self.position['type'] == 'short':
            pnl = -pnl
        self.capital += pnl
        self.trades[-1].update({
            'exit_price': price,
            'exit_time': timestamp,  # ← Fecha/hora de salida
            'pnl': pnl,
            'reason': reason
        })
        save_trade(self.trades[-1])
        print(f"  🔴 Cierre ({reason}) | "
            f"Salida: {timestamp.strftime('%Y-%m-%d %H:%M')} a ${price:.2f} | "
            f"PnL: ${pnl:+.2f} | Capital: ${self.capital:.2f}")
        self.position = None

    def _print_summary(self):
        closed_trades = [t for t in self.trades if 'pnl' in t]
        if not closed_trades:
            print("\n⚠️  Ningún trade cerrado.")
            return

        df_trades = pd.DataFrame(closed_trades)
        total_pnl = df_trades['pnl'].sum()
        win_rate = (df_trades['pnl'] > 0).mean() * 100
        total_trades = len(df_trades)

        print("\n" + "="*50)
        print("🤖 RESUMEN DEL BACKTEST CON ML")
        print("="*50)
        print(f"Capital inicial: ${self.initial_capital:.2f}")
        print(f"Capital final:   ${self.capital:.2f}")
        print(f"Ganancia neta:   ${total_pnl:+.2f} ({total_pnl/self.initial_capital*100:+.2f}%)")
        print(f"Total de trades: {total_trades}")
        print(f"Win rate:        {win_rate:.1f}%")
        print("="*50)

    def _plot_equity_curve(self):
        if not self.equity_curve:
            return
        times, capitals = zip(*self.equity_curve)
        plt.figure(figsize=(12, 6))
        plt.plot(times, capitals, color='#1f77b4', linewidth=2)
        plt.title(f'Curva de Capital - ML Model ({self.symbol})', fontsize=14)
        plt.ylabel('Capital (USDT)')
        plt.grid(True, alpha=0.3)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    symbol_to_use = "BTC/USDT:USDT" if TRADING_MODE == "futures" else SYMBOL
    
    print("⏳ Descargando datos para backtest ML...")
    df = fetch_ohlcv(symbol_to_use, "1h", limit=10000)  # 1000 horas = ~41 días

    if df.empty:
        print("❌ Error al cargar datos.")
    else:
        agent = MLBacktester(symbol_to_use, "1h", INITIAL_CAPITAL)
        agent.run_backtest(df)