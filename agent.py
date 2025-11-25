import pandas as pd
import logging
from config import SYMBOL, TRADING_MODE, INITIAL_CAPITAL, MODE, SIGNAL_TIMEFRAME, EXECUTION_TIMEFRAME, LEVERAGE
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
        self.position = None
        self.trades = []
        self.trade_count = 0
        self.params = load_best_params()
        self.ml_agent = MLAgent()
        self.executor = TradeExecutor(SYMBOL)
        self.last_signal = None
        self.signal_timeframe = SIGNAL_TIMEFRAME
        self.execution_timeframe = EXECUTION_TIMEFRAME
        self.last_cleanup = pd.Timestamp.now(tz='UTC')
        
        # 🔑 ¡CLAVE PARA MODO LIVE!
        if MODE == "live":
            real_balance = self.executor.get_account_balance()
            if real_balance > 0:
                self.capital = real_balance
                logging.info(f"💰 Capital real cargado: ${self.capital:.2f}")
            else:
                logging.warning("⚠️ No se pudo obtener saldo real. Usando INITIAL_CAPITAL como fallback.")
                self.capital = INITIAL_CAPITAL
        else:
            self.capital = INITIAL_CAPITAL
            logging.info(f"🎭 Capital en modo paper: ${self.capital:.2f}")
        
        logging.info(f"🧠 Agente iniciado | Señales: {SIGNAL_TIMEFRAME} | Ejecución: {EXECUTION_TIMEFRAME}")

    def _update_real_capital(self):
        """Actualiza el capital con el saldo real de Binance"""
        if MODE != "live" or not hasattr(self.executor, 'exchange') or not self.executor.exchange:
            return
        
        try:
            # ✅ Obtener saldo REAL incluyendo todas las comisiones y fees
            real_balance = self.executor.get_account_balance()
            
            # Solo actualizar si hay cambio significativo (>0.01 USDT)
            if abs(real_balance - self.capital) > 0.01:
                old_capital = self.capital
                self.capital = real_balance
                logging.info(f"💰 CAPITAL ACTUALIZADO | Antes: ${old_capital:.2f} | Ahora: ${self.capital:.2f} | Diferencia: ${self.capital - old_capital:.2f}")
            
            # Protección: si el capital es muy bajo
            if self.capital < 10.0:  # $10 mínimo
                logging.warning(f"⚠️ CAPITAL MUY BAJO: ${self.capital:.2f}. Reduciendo riesgo...")
                self.params['risk_per_trade'] = 0.005  # 0.5% máximo
                
        except Exception as e:
            logging.error(f"❌ Error al actualizar capital real: {str(e)}")
    
    def _should_exit_position(self, df, entry_price, position_type, atr_multiple=1.5):
        """Simula cierre por SL/TP considerando HIGH/LOW de la vela (más realista)"""
        last = df.iloc[-1]
        atr = last['atr']
        
        if position_type == 'long':
            sl = entry_price - atr * atr_multiple
            tp = entry_price + atr * atr_multiple * 2
            # Verificar si el precio TOCÓ el SL/TP durante la vela
            sl_hit = last['low'] <= sl  # ¡Usa LOW en vez de CLOSE!
            tp_hit = last['high'] >= tp  # ¡Usa HIGH en vez de CLOSE!
        else:  # short
            sl = entry_price + atr * atr_multiple
            tp = entry_price - atr * atr_multiple * 2
            sl_hit = last['high'] >= sl  # ¡Usa HIGH en vez de CLOSE!
            tp_hit = last['low'] <= tp  # ¡Usa LOW en vez de CLOSE!
        
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
        """Verifica posición en Binance y limpia órdenes huérfanas"""
        try:
            if MODE == "live" and TRADING_MODE == "futures":
                # 1. Obtener posiciones actuales
                positions = self.executor.exchange.fetch_positions([self.symbol])
                open_positions = [p for p in positions if float(p['contracts']) > 0]
                
                # 2. Verificar si hay discrepancia con el estado local
                position_exists_remotely = len(open_positions) > 0
                position_exists_locally = self.position is not None
                
                if position_exists_remotely and not position_exists_locally:
                    logging.warning("⚠️ Posición abierta en Binance pero no en el bot. Syncronizando...")
                    # Aquí podrías reconstruir el estado local basado en Binance
                    self._sync_position_from_exchange(open_positions[0])
                
                elif not position_exists_remotely and position_exists_locally:
                    logging.warning("⚠️ Posición cerrada externamente. Limpiando estado local y órdenes...")
                    # ✅ SOLUCIÓN: Cancelar órdenes ANTES de cerrar estado local
                    self.executor.cancel_associated_orders(self.symbol)
                    # Forzar cierre de posición local
                    current_price = self.executor.exchange.fetch_ticker(self.symbol)['last']
                    self._close_position(current_price, 'closed_externally')
                    return
                
                # 3. Si no hay posición abierta, limpiar órdenes huérfanas
                if not position_exists_remotely:
                    self.executor.cancel_associated_orders(self.symbol)
                    
        except Exception as e:
            logging.warning(f"⚠️ Error al verificar posición: {str(e)}")

    def run_once(self):
        try:
            # 🔑 Actualizar capital real en modo live
            self._update_real_capital()

            logging.info("💓 Evaluando mercado...")
            

            # Descargar datos de ejecución (5m)
            df_exec = fetch_ohlcv(self.symbol, self.execution_timeframe)
            if df_exec.empty:
                logging.warning("⚠️ Datos de ejecución vacíos, saltando ciclo")
                return
            df_exec = add_indicators(df_exec)
            current_time = df_exec.index[-1]
            
            # 💡 DEFINIR current_price AQUÍ (siempre existe si df_exec no está vacío)
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
                        # Asegurar zona horaria UTC
                        signal_time = df_signal.index[-1]
                        if signal_time.tzinfo is None:
                            signal_time = signal_time.tz_localize('UTC')
                        
                        self.last_signal = {
                            'direction': signal_dir,
                            'price': df_signal['close'].iloc[-1],
                            'time': signal_time,
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
            
            # 👇 SECCIÓN CORREGIDA DE DEPURACIÓN PARA POSICIÓN ABIERTA
            if self.position is not None:
                # Mostrar estado actual de la posición
                sl_hit, tp_hit, sl, tp = self._should_exit_position(
                    df_exec, self.position['entry'], self.position['type'], self.params['atr_multiple']
                )
                logging.info(f"🔍 Posición abierta | Precio actual: ${current_price:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")
                logging.info(f"📊 Vela completa - HIGH: ${df_exec['high'].iloc[-1]:.2f} | LOW: ${df_exec['low'].iloc[-1]:.2f}")
                logging.info(f"🎯 ¿SL tocado? {sl_hit} | ¿TP tocado? {tp_hit}")
                
                # Cerrar en modo paper si se cumple SL/TP
                if MODE == "paper" and (sl_hit or tp_hit):
                    self._close_position(current_price, 'SL' if sl_hit else 'TP')
                    
            # 🔁 LIMPIEZA PERIÓDICA: Cada 5 minutos
            if hasattr(self, 'last_cleanup') and (pd.Timestamp.now(tz='UTC') - self.last_cleanup).total_seconds() > 300:
                logging.info("🧹 Ejecutando limpieza periódica de órdenes huérfanas...")
                self.executor.cancel_associated_orders(self.symbol)
                self.last_cleanup = pd.Timestamp.now(tz='UTC')

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
            logging.warning("⚠️ Tamaño de posición <= 0, operación cancelada")
            return

        # ✅ VERIFICACIÓN FINAL: margen suficiente
        required_margin = (size * entry_price) / LEVERAGE
        if required_margin > self.capital * 0.95:
            logging.critical(
                f"❌ IMPOSIBLE ABRIR POSICIÓN | "
                f"Margen requerido: ${required_margin:.2f} | "
                f"Capital disponible: ${self.capital:.2f} | "
                f"Tamaño ajustado a 0"
            )
            return  # ¡NO ENVIAR ORDEN!

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
        try:
            # ✅ PASO 1: Cancelar TODAS las órdenes asociadas ANTES de cerrar
            if MODE == "live" and TRADING_MODE == "futures":
                logging.info("🧹 Cancelando TODAS las órdenes asociadas antes de cerrar posición...")
                self.executor.cancel_all_associated_orders(self.symbol)
           
            # Calcular PnL con datos locales (para logging)
            pnl = (price - self.position['entry']) * self.position['size']
            if self.position['type'] == 'short':
                pnl = -pnl
            
            # Guardar capital anterior para logging
            old_capital = self.capital
            
            # ✅ ACTUALIZAR CAPITAL DESDE BINANCE (después de cerrar)
            self._update_real_capital()
            
            # Calcular PnL real basado en cambio de capital
            real_pnl = self.capital - old_capital
            trade_record = {
                'exit_price': price,
                'pnl': real_pnl,
                'reason': reason,
                'commission_included': True
            }
            self.trades[-1].update(trade_record)
            save_trade(self.trades[-1])
            
            # Cerrar posición en el exchange (si es necesario)
            close_side = 'sell' if self.position['type'] == 'long' else 'buy'
            self.executor.close_position(self.position['size'], close_side)
            
            # Mensaje con PnL real (incluyendo comisiones)
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = (
                f"CloseOperation ({reason})\n"
                f"Fecha: {current_time}\n"
                f"PnL REAL: ${real_pnl:.2f} (Capital: ${old_capital:.2f} → ${self.capital:.2f})"
            )
            logging.info(msg.replace('\n', ' | '))
            send_telegram_message(msg)
            
            self.position = None
            self.trade_count += 1
            
        except Exception as e:
            logging.error(f"❌ Error al cerrar posición y actualizar capital: {str(e)}")