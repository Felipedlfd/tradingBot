import pandas as pd
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from config import SYMBOL, TIMEFRAME, INITIAL_CAPITAL, TRADING_MODE
from data import fetch_ohlcv
from indicators import add_indicators
from strategy import should_enter_long, should_enter_short, should_exit_position
from risk_manager import calculate_position_size
from utils import save_trade
from strategy_factory import STRATEGIES
from strategy_selector import load_best_strategy

# Configurar logging silencioso
logging.basicConfig(level=logging.WARNING)

class BacktestAgent:
    def __init__(self, symbol, timeframe, capital):
        self.symbol = symbol
        self.timeframe = timeframe
        self.capital = capital
        self.initial_capital = capital
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.params = {
            'atr_multiple': 1.5,
            'risk_per_trade': 0.01
        }
        # Cargar estrategia
        best_strategy = load_best_strategy()
        self.strategy_func = STRATEGIES[best_strategy['name']]
        print(f"🧠 Backtest usando estrategia: {best_strategy['name']}")

    def run_backtest(self, df):
        print(f"📊 Iniciando backtest rápido en {self.timeframe} para {self.symbol}")
        print(f"📈 Velas cargadas: {len(df)} ({df.index[0]} → {df.index[-1]})\n")

        # Iniciar curva de equity
        self.equity_curve.append((df.index[0], self.capital))

        for i in range(200, len(df)):
            current_df = df.iloc[:i+1].copy()
            current_df = add_indicators(current_df)
            current_price = current_df['close'].iloc[-1]
            current_time = df.index[i]

            # Cerrar posición si se alcanza SL/TP
            if self.position:
                sl_hit, tp_hit, sl, tp = should_exit_position(
                    current_df, self.position['entry'], self.position['type'], self.params['atr_multiple']
                )
                if sl_hit or tp_hit:
                    self._close_position(current_price, 'SL' if sl_hit else 'TP', current_time)
            
            # Registrar capital actual
            self.equity_curve.append((current_time, self.capital))

            # Abrir nueva posición si no hay una
            if self.position is None:
                # 👇 NUEVO: Usar la estrategia seleccionada
                signal = self.strategy_func(current_df, self.params)
                if signal == 'long':
                    self._open_position(current_df, 'long')
                elif signal == 'short' and TRADING_MODE == "futures":
                    self._open_position(current_df, 'short')

        self._print_summary()
        self._plot_equity_curve()

    def _open_position(self, df, pos_type):
        last = df.iloc[-1]
        entry_price = last['close']
        atr = last['atr']
        sl = entry_price - atr * self.params['atr_multiple'] if pos_type == 'long' else entry_price + atr * self.params['atr_multiple']
        size = calculate_position_size(self.capital, entry_price, sl, self.params['risk_per_trade'])
        if size <= 0:
            return

        self.position = {
            'type': pos_type,
            'size': size,
            'entry': entry_price,
            'sl': sl
        }
        self.trades.append({
            'type': pos_type,
            'price': entry_price,
            'size': size,
            'timestamp': df.index[-1]
        })
        print(f"🟢 {'LONG' if pos_type == 'long' else 'SHORT'} en {df.index[-1].strftime('%H:%M')} a ${entry_price:.2f}")

    def _close_position(self, price, reason, timestamp):
        pnl = (price - self.position['entry']) * self.position['size']
        if self.position['type'] == 'short':
            pnl = -pnl
        self.capital += pnl
        self.trades[-1].update({
            'exit_price': price,
            'pnl': pnl,
            'reason': reason,
            'timestamp': timestamp
        })
        save_trade(self.trades[-1])
        print(f"  🔴 Cierre ({reason}) → PnL: ${pnl:+.2f} | Capital: ${self.capital:.2f}")
        self.position = None

    def _print_summary(self):
        if not self.trades:
            print("\n❌ No se generaron señales en este periodo.")
            return

        closed_trades = [t for t in self.trades if 'pnl' in t]
        if not closed_trades:
            print("\n⚠️  Trades abiertos, pero ninguno cerrado.")
            return

        df_trades = pd.DataFrame(closed_trades)
        total_pnl = df_trades['pnl'].sum()
        win_rate = (df_trades['pnl'] > 0).mean() * 100
        total_trades = len(df_trades)

        print("\n" + "="*50)
        print("📈 RESUMEN DEL BACKTEST")
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
        plt.plot(times, capitals, color='#2E8B57', linewidth=2)
        plt.title(f'Curva de Capital - {self.symbol} ({self.timeframe})', fontsize=14)
        plt.ylabel('Capital (USDT)')
        plt.grid(True, alpha=0.3)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=6))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

# Usa el mismo timeframe que en config.py, o define uno aquí
BACKTEST_TIMEFRAME = "1h"  # ← cámbialo a "1h", "4h", etc.

if __name__ == "__main__":
    # Asegurar que el símbolo sea compatible
    symbol_to_use = SYMBOL
    if TRADING_MODE == "futures" and SYMBOL == "BTC/USDT":
        symbol_to_use = "BTC/USDT:USDT"

    print(f"⏳ Descargando datos históricos de {BACKTEST_TIMEFRAME} ...")
    df = fetch_ohlcv(symbol_to_use, BACKTEST_TIMEFRAME, limit=3000)

    if df.empty:
        print("❌ Error: No se pudieron cargar los datos.")
    else:
        agent = BacktestAgent(symbol_to_use, BACKTEST_TIMEFRAME, INITIAL_CAPITAL)
        agent.run_backtest(df)

        # Opcional: abrir dashboard
        import os
        open_dash = input("\n¿Abrir dashboard para ver resultados? (s/n): ").strip().lower()
        if open_dash == 's':
            os.system("start_dashboard.bat")

        # Al final del backtest, pregunta si quieres optimizar
        optimize_now = input("\n¿Quieres que el agente aprenda de este backtest y ajuste su estrategia? (s/n): ").strip().lower()
        if optimize_now == 's':
            from learner import optimize_parameters
            symbol_opt = "BTC/USDT:USDT" if TRADING_MODE == "futures" else "BTC/USDT"
            optimize_parameters(symbol=symbol_opt, trading_mode=TRADING_MODE, days=2)