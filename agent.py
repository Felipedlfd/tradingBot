# agent.py
import pandas as pd
import logging
from config import SYMBOL, TRADING_MODE, INITIAL_CAPITAL, MODE, SIGNAL_TIMEFRAME, EXECUTION_TIMEFRAME
from data import fetch_ohlcv
from indicators import add_indicators
from risk_manager import calculate_position_size
from learner import load_best_params
from executor import TradeExecutor
from notifier import send_telegram_message
from utils import save_trade
from ml_agent import MLAgent

class CryptoAgent:
    def __init__(self):
        self.symbol = SYMBOL
        self.trading_mode = TRADING_MODE
        self.capital = INITIAL_CAPITAL
        self.position = None
        self.trades = []
        self.trade_count = 0
        self.params = load_best_params()
        self.ml_agent = MLAgent()
        self.executor = TradeExecutor(SYMBOL)
        self.last_signal = None
        self.signal_timeframe = SIGNAL_TIMEFRAME
        self.execution_timeframe = EXECUTION_TIMEFRAME
        logging.info(f"🧠 Agente iniciado | Señales: {SIGNAL_TIMEFRAME} | Ejecución: {EXECUTION_TIMEFRAME}")

    def _should_exit_position(self, df, entry_price, position_type, atr_multiple=1.5):
        """Simula cierre por SL/TP (solo para modo paper)"""
        last = df.iloc[-1]
        atr = last['atr']
        if position_type == 'long':
            sl = entry_price - atr * atr_multiple
            tp = entry_price + atr * atr_multiple * 2
            sl_hit = last['close'] <= sl
            tp_hit = last['close'] >= tp
        else:  # short
            sl = entry_price + atr * atr_multiple
            tp = entry_price - atr * atr_multiple * 2
            sl_hit = last['close'] >= sl
            tp_hit = last['close'] <= tp
        return sl_hit, tp_hit, sl, tp

    def _is_signal_time(self, current_time):
        """Verifica si es momento de generar señal (al inicio de cada período de señal)"""
        # Asegurar zona horaria UTC
        if current_time.tzinfo is None:
            current_time = current_time.tz_localize('UTC')
        
        if self.signal_timeframe == "1h":
            return current_time.minute == 0
        elif self.signal_timeframe == "4h":
            return current_time.hour % 4 == 0 and current_time.minute == 0
        elif self.signal_timeframe == "1d":
            return current_time.hour == 0 and current_time.minute == 0
        return True

    def _is_signal_still_valid(self, signal, current_price, current_atr):
        """Verifica que la señal no esté vencida"""
        # Asegurar zona horaria UTC en el tiempo de la señal
        signal_time = signal['time']
        if signal_time.tzinfo is None:
            signal_time = signal_time.tz_localize('UTC')
        
        current_time = pd.Timestamp.now(tz='UTC')
        
        # 1. Tiempo máximo: 30 minutos para señales de 1h
        signal_age = (current_time - signal_time).total_seconds() / 60
        max_age = 30 if self.signal_timeframe == "1h" else 120
        if signal_age > max_age:
            return False
        
        # 2. Movimiento de precio: no más de 0.5 ATR desde la señal
        price_move = abs(current_price - signal['price'])
        if price_move > 0.5 * signal['atr']:
            return False
        
        # 3. Dirección: el precio debe seguir en la dirección de la señal
        if signal['direction'] == 'long' and current_price < signal['price']:
            return False
        if signal['direction'] == 'short' and current_price > signal['price']:
            return False
            
        return True

    def _check_position_status(self):
        """Verifica posición en Binance (solo live)"""
        try:
            if MODE == "live" and TRADING_MODE == "futures":
                positions = self.executor.exchange.fetch_positions([self.symbol])
                open_positions = [p for p in positions if float(p['contracts']) > 0]
                if not open_positions and self.position:
                    current_price = self.executor.exchange.fetch_ticker(self.symbol)['last']
                    self._close_position(current_price, 'closed_by_exchange')
        except Exception as e:
            logging.warning(f"No se pudo verificar posición: {e}")

    def run_once(self):
        try:
            logging.info("💓 Evaluando mercado...")
            
            # Descargar datos de ejecución (5m)
            df_exec = fetch_ohlcv(self.symbol, self.execution_timeframe)
            if df_exec.empty:
                return
            df_exec = add_indicators(df_exec)
            current_time = df_exec.index[-1]
            current_price = df_exec['close'].iloc[-1]
            
            # En live: verificar si la posición sigue abierta
            if MODE == "live" and self.position is not None:
                self._check_position_status()
                if self.position is None:
                    return
            
            # Generar nueva señal si es momento
            if self._is_signal_time(current_time) and self.position is None:
                df_signal = fetch_ohlcv(self.symbol, self.signal_timeframe)
                if not df_signal.empty:
                    df_signal = add_indicators(df_signal)
                    signal_dir = self.ml_agent.get_signal_from_dataframe(df_signal)
                    if signal_dir in ['long', 'short']:
                        # 👇 AQUÍ: Asegurar zona horaria UTC
                        signal_time = df_signal.index[-1]
                        if signal_time.tzinfo is None:
                            signal_time = signal_time.tz_localize('UTC')

                        self.last_signal = {
                            'direction': signal_dir,
                            'price': df_signal['close'].iloc[-1],
                            'time': df_signal.index[-1],
                            'atr': df_signal['atr'].iloc[-1]
                        }
                        logging.info(f"✅ Nueva señal {signal_dir.upper()} detectada")
            
            # Ejecutar señal si está disponible y es válida
            if self.last_signal and self.position is None:
                if self._is_signal_still_valid(self.last_signal, current_price, df_exec['atr'].iloc[-1]):
                    if self.last_signal['direction'] == 'long':
                        self._open_position(df_exec, 'long')
                    elif self.last_signal['direction'] == 'short' and TRADING_MODE == "futures":
                        self._open_position(df_exec, 'short')
                    self.last_signal = None  # Consumir la señal
                else:
                    logging.info("⚠️ Señal obsoleta, ignorando...")
                    self.last_signal = None
                    
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

        # Enviar orden (OCO en live, simple en paper)
        if MODE == "live":
            self.executor.place_order(
                side='buy' if pos_type == 'long' else 'sell',
                amount=size,
                sl_price=sl,
                tp_price=tp
            )
        else:
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
            'strategy': 'ml_hybrid'
        }
        self.trades.append(trade_record)
        
        # Mensaje con detalles
        risk_amount = self.capital * self.params['risk_per_trade']
        msg = (
            f"🤖 NUEVO {pos_type.upper()} (Híbrido)\n"
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
        
        # Mensaje de cierre
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