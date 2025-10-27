# agent.py
import pandas as pd
import logging
from config import SYMBOL, TIMEFRAME, INITIAL_CAPITAL, MODE, TRADING_MODE, OPTIMIZE_EVERY
from data import fetch_ohlcv
from indicators import add_indicators
from risk_manager import calculate_position_size
from learner import load_best_params
from executor import TradeExecutor
from notifier import send_telegram_message
from utils import save_trade
from strategy_factory import STRATEGIES
from strategy_selector import load_best_strategy
from ml_agent import MLAgent
from strategy import should_exit_position

class CryptoAgent:
    def __init__(self):
        # ... código anterior ...
        self.symbol = SYMBOL
        self.trading_mode = TRADING_MODE
        self.capital = INITIAL_CAPITAL
        self.position = None  # ← ¡Esta línea es obligatoria!
        self.ml_agent = MLAgent()  # ← instancia el agente ML
        logging.info("🧠 Usando modelo ML para señales")

    def run_once(self):
        try:
            logging.info("💓 Evaluando mercado...")  # ← Añade esta línea
            df = fetch_ohlcv(self.symbol, TIMEFRAME)
            df = add_indicators(df)
            
            # 👇 Usa SOLO el modelo ML
            signal = self.ml_agent.get_signal(self.symbol, TIMEFRAME)
            
            if self.position is None:
                if signal == 'long':
                    self._open_position(df, 'long')
                elif signal == 'short' and TRADING_MODE == "futures":
                    self._open_position(df, 'short')
            else:
                # Lógica de cierre (SL/TP)
                current_price = df['close'].iloc[-1]
                sl_hit, tp_hit, sl, tp = should_exit_position(
                    df, self.position['entry'], self.position['type'], self.params['atr_multiple']
                )
                if sl_hit or tp_hit:
                    self._close_position(current_price, 'SL' if sl_hit else 'TP')
        except Exception as e:
            logging.error(f"Error en run_once: {e}", exc_info=True)

    def _open_position(self, df, pos_type):
        last = df.iloc[-1]
        entry_price = last['close']
        atr = last['atr']
        sl = entry_price - atr * self.params['atr_multiple'] if pos_type == 'long' else entry_price + atr * self.params['atr_multiple']
        tp = entry_price + (entry_price - sl) * 2 if pos_type == 'long' else entry_price - (sl - entry_price) * 2
        size = calculate_position_size(self.capital, entry_price, sl, self.params['risk_per_trade'])
        if size <= 0:
            return

        side = 'buy' if pos_type == 'long' else 'sell'
        self.executor.place_order(side, size, entry_price)

        self.position = {
            'type': pos_type,
            'size': size,
            'entry': entry_price,
            'sl': sl,
            'tp': tp
        }
        trade_record = {
            'type': pos_type,
            'price': entry_price,
            'size': size,
            'timestamp': df.index[-1],
            'strategy': 'ml_model'
        }
        self.trades.append(trade_record)
        
        # 👇 Mensaje mejorado con SL, TP y riesgo
        risk_amount = self.capital * self.params['risk_per_trade']
        msg = (
            f"🤖 NUEVO {pos_type.upper()}\n"
            f"Símbolo: {self.symbol}\n"
            f"Precio: ${entry_price:.2f}\n"
            f"Tamaño: {size:.6f} ({size * entry_price:.2f} USDT)\n"
            f"SL: ${sl:.2f} | TP: ${tp:.2f}\n"
            f"Riesgo: ${risk_amount:.2f} ({self.params['risk_per_trade']*100:.1f}% del capital)"
        )
        logging.info(msg.replace('\n', ' | '))
        send_telegram_message(msg)

    def _close_position(self, price, reason):
        pnl = (price - self.position['entry']) * self.position['size']
        if self.position['type'] == 'short':
            pnl = -pnl
        self.capital += pnl
        trade_record = {
            'exit_price': price,
            'pnl': pnl,
            'reason': reason
        }
        self.trades[-1].update(trade_record)
        save_trade(self.trades[-1])
        close_side = 'sell' if self.position['type'] == 'long' else 'buy'
        self.executor.close_position(self.position['size'], close_side)
        
        # 👇 Mensaje mejorado con fecha y hora
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"CloseOperation ({reason})\n"
            f"Fecha: {current_time}\n"
            f"PnL: ${pnl:.2f} | Capital: ${self.capital:.2f}"
        )
        logging.info(msg.replace('\n', ' | '))
        send_telegram_message(msg)
        self.position = None
        self.trade_count += 1