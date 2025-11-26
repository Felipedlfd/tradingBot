# executor.py
import ccxt
import logging
import pandas as pd
import time
from config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE, TRADING_MODE, LEVERAGE

class TradeExecutor:
    def __init__(self, symbol):
        self.symbol = symbol
        self.exchange = None
        self._init_exchange()
        logging.info(f"💱 Ejecutor inicializado para {symbol} en modo {TRADING_MODE}")

    def _init_exchange(self):
        """Inicializa la conexión con Binance y carga los mercados"""
        if MODE == "live":
            exchange_config = {
                'apiKey': BINANCE_API_KEY,
                'secret': BINANCE_API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'adjustForTimeDifference': True,
                    'defaultType': 'future' if TRADING_MODE == "futures" else 'spot',
                    'warnOnFetchOpenOrdersWithoutSymbol': False
                }
            }
            
            if TRADING_MODE == "futures":
                self.exchange = ccxt.binanceusdm(exchange_config)
                logging.info("🚀 Conectado a Binance USD-M Futures")
            else:
                self.exchange = ccxt.binance(exchange_config)
                logging.info("🚀 Conectado a Binance Spot")
            
            try:
                self.exchange.load_markets()
                logging.info("✅ Mercados cargados correctamente")
            except Exception as e:
                logging.warning(f"⚠️ Error al cargar mercados: {str(e)}")
        else:
            logging.info("🎭 Modo PAPER: Sin conexión real a Binance")

    def _normalize_symbol(self, symbol):
        """Convierte el símbolo al formato correcto para Binance API"""
        normalized = symbol.replace("/", "").replace(":", "").replace("-", "").upper()
        logging.info(f"🔄 Normalizando símbolo: '{symbol}' → '{normalized}'")
        return normalized

    def _set_leverage(self):
        """Configura el apalancamiento para futures (solo en modo live)"""
        if MODE != "live" or TRADING_MODE != "futures" or not self.exchange:
            return
        
        try:
            # Asegurar que los mercados están cargados
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                self.exchange.load_markets()
            
            normalized_symbol = self._normalize_symbol(self.symbol)
            market = self.exchange.market(normalized_symbol)
            symbol_id = market['id']
            
            self.exchange.set_leverage(LEVERAGE, symbol_id)
            logging.info(f"⚙️ Apalancamiento configurado a {LEVERAGE}x para {self.symbol}")
        except Exception as e:
            logging.warning(f"⚠️ No se pudo establecer apalancamiento: {str(e)}")
            logging.warning("ℹ️ Continuando sin cambiar apalancamiento. Verifica en Binance Web.")

    def get_account_balance(self):
        """Obtiene el saldo disponible en USDT para trading"""
        try:
            if MODE != "live" or not self.exchange:
                return 1000.0  # Saldo simulado en modo paper
            
            if TRADING_MODE == "futures":
                # ✅ MÉTODO CORRECTO PARA FUTURES EN CCXT
                balance = self.exchange.fetch_balance()
                if 'USDT' in balance and isinstance(balance['USDT'], dict):
                    usdt_balance = balance['USDT'].get('total', 0.0)
                elif hasattr(balance, 'USDT') and hasattr(balance.USDT, 'total'):
                    usdt_balance = balance.USDT.total
                else:
                    usdt_balance = 0.0
                return float(usdt_balance)
            else:
                # Para spot
                balance = self.exchange.fetch_balance()
                if 'USDT' in balance and isinstance(balance['USDT'], dict):
                    usdt_balance = balance['USDT'].get('free', 0.0)
                else:
                    usdt_balance = 0.0
                return float(usdt_balance)
        except Exception as e:
            logging.error(f"❌ Error al obtener saldo real: {str(e)}")
            return 1000.0  # Valor por defecto seguro

    def fetch_positions(self, symbol=None):
        """Obtiene posiciones abiertas (solo para futures en modo live)"""
        if MODE != "live" or TRADING_MODE != "futures" or not self.exchange:
            return []
        
        try:
            # ✅ MÉTODO CORRECTO EN CCXT
            if symbol:
                normalized_symbol = self._normalize_symbol(symbol)
                positions = self.exchange.fetch_positions([normalized_symbol])
            else:
                positions = self.exchange.fetch_positions()
            
            return [p for p in positions if float(p['contracts']) > 0]
        except Exception as e:
            logging.warning(f"⚠️ Error al obtener posiciones: {str(e)}")
            return []

    def cancel_order_if_exists(self, order_id, symbol):
        """Cancela una orden SOLO si existe y está abierta"""
        if not order_id:
            return False
        
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            order = self.exchange.fetch_order(order_id, normalized_symbol)
            
            if order['status'] in ['open', 'partially_filled']:
                self.exchange.cancel_order(order_id, normalized_symbol)
                logging.info(f"✅ Orden cancelada correctamente | ID: {order_id} | Estado: {order['status']}")
                return True
            else:
                logging.info(f"ℹ️ Orden ya cerrada | ID: {order_id} | Estado: {order['status']}")
                return False
        except Exception as e:
            if 'Order does not exist' in str(e) or 'Unknown order sent' in str(e):
                logging.info(f"ℹ️ Orden ya ejecutada o cancelada | ID: {order_id}")
                return False
            logging.warning(f"⚠️ Error cancelando orden {order_id}: {str(e)}")
            return False

    def get_open_orders_for_symbol(self, symbol):
        """Obtiene todas las órdenes abiertas para un símbolo"""
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            return self.exchange.fetch_open_orders(normalized_symbol)
        except Exception as e:
            logging.error(f"❌ Error obteniendo órdenes abiertas: {str(e)}")
            return []

    def place_order(self, side, amount, price=None, sl_price=None, tp_price=None):
        """
        Ejecuta órdenes en Binance USD-M Futures con gestión robusta de SL/TP
        """
        if MODE == "paper":
            # Modo paper: solo imprimir
            order_type = "MARKET"
            if sl_price and tp_price:
                order_type = "OCO (simulado)"
            print(f"[PAPER] {side.upper()} {amount:.6f} de {self.symbol} | Tipo: {order_type}")
            if sl_price and tp_price:
                print(f"  📌 SL: {sl_price:.2f} | TP: {tp_price:.2f} (simulados)")
            return {
                'market_order': {'id': 'paper_order'},
                'sl_order_id': 'paper_sl',
                'tp_order_id': 'paper_tp',
                'id': 'paper_order'
            }
        
        else:
            try:
                if TRADING_MODE == "futures":
                    normalized_symbol = self._normalize_symbol(self.symbol)
                    self._set_leverage()
                    
                    # 1. Abrir posición con orden de mercado
                    logging.info(f"🔵 Abriendo posición MARKET: {side.upper()} {amount} {normalized_symbol}")
                    market_order = self.exchange.create_order(
                        symbol=normalized_symbol,
                        type='MARKET',
                        side=side.upper(),
                        amount=amount
                    )
                    market_order_id = market_order.get('id', 'N/A')
                    logging.info(f"✅ Posición abierta: {side.upper()} {amount:.6f} de {normalized_symbol} | ID: {market_order_id}")
                    
                    # 2. Crear órdenes SL/TP por separado
                    sl_order_id = None
                    tp_order_id = None
                    
                    if sl_price is not None:
                        sl_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        logging.info(f"🛑 Creando Stop Loss: {sl_side} {amount} @ {sl_price}")
                        try:
                            sl_order = self.exchange.create_order(
                                symbol=normalized_symbol,
                                type='STOP_MARKET',
                                side=sl_side,
                                amount=amount,
                                params={
                                    'stopPrice': sl_price,
                                    'closePosition': True,  # Cierra TODA la posición
                                    'workingType': 'CONTRACT_PRICE',
                                    'priceProtect': True
                                }
                            )
                            sl_order_id = sl_order.get('id', 'N/A')
                            logging.info(f"🛑 Stop Loss creado | ID: {sl_order_id} | Precio: {sl_price:.2f}")
                        except Exception as e:
                            logging.error(f"❌ Error creando Stop Loss: {str(e)}")
                    
                    if tp_price is not None:
                        tp_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        logging.info(f"🎯 Creando Take Profit: {tp_side} {amount} @ {tp_price}")
                        try:
                            tp_order = self.exchange.create_order(
                                symbol=normalized_symbol,
                                type='TAKE_PROFIT_MARKET',
                                side=tp_side,
                                amount=amount,
                                params={
                                    'stopPrice': tp_price,
                                    'closePosition': True,  # Cierra TODA la posición
                                    'workingType': 'CONTRACT_PRICE',
                                    'priceProtect': True
                                }
                            )
                            tp_order_id = tp_order.get('id', 'N/A')
                            logging.info(f"🎯 Take Profit creado | ID: {tp_order_id} | Precio: {tp_price:.2f}")
                        except Exception as e:
                            logging.error(f"❌ Error creando Take Profit: {str(e)}")
                    
                    # 3. Devolver IDs para seguimiento
                    return {
                        'market_order': market_order,
                        'sl_order_id': sl_order_id,
                        'tp_order_id': tp_order_id,
                        'id': market_order_id,
                        'symbol': normalized_symbol
                    }
                
                else:
                    # Spot: órdenes simples
                    order = self.exchange.create_market_order(self.symbol, side.upper(), amount)
                    logging.info(f"✅ Orden SPOT LIVE: {side.upper()} {amount:.6f}")
                    return order
                    
            except Exception as e:
                error_msg = f"❌ Error en orden LIVE ({side.upper()} {amount:.6f}): {str(e)}"
                logging.error(error_msg)
                return None

    def close_position_with_protection(self, amount, side="sell", active_orders=None):
        """
        Cierra posición con protección para SL/TP
        active_orders: {'sl_order_id': 'id1', 'tp_order_id': 'id2'}
        """
        if MODE == "paper":
            print(f"[PAPER] CIERRE {side.upper()} {amount:.6f} de {self.symbol}")
            return {"status": "filled", "id": "paper_close"}
        
        if TRADING_MODE == "futures":
            try:
                normalized_symbol = self._normalize_symbol(self.symbol)
                
                # 1. Primero cancelar SOLO las órdenes que aún están activas
                if active_orders:
                    logging.info("🛡️ Protegiendo órdenes SL/TP antes de cerrar posición...")
                    
                    # Cancelar SOLO si las órdenes aún existen
                    if active_orders.get('sl_order_id'):
                        self.cancel_order_if_exists(active_orders['sl_order_id'], normalized_symbol)
                    
                    if active_orders.get('tp_order_id'):
                        self.cancel_order_if_exists(active_orders['tp_order_id'], normalized_symbol)
                
                # 2. Cerrar posición con reduceOnly
                logging.info(f"CloseOperation: {side.upper()} {amount:.6f} de {normalized_symbol}")
                order = self.exchange.create_order(
                    symbol=normalized_symbol,
                    type='MARKET',
                    side=side.upper(),
                    amount=amount,
                    params={'reduceOnly': True}
                )
                order_id = order.get('id', 'N/A')
                logging.info(f"✅ Posición cerrada | ID: {order_id}")
                return order
                
            except Exception as e:
                # Manejo especial para "ReduceOnly Order is rejected"
                if "2022" in str(e) or "ReduceOnly Order is rejected" in str(e):
                    logging.warning("⚠️ Posición ya cerrada externamente. Verificando estado...")
                    return {"status": "already_closed"}
                
                logging.error(f"❌ Error al cerrar posición: {str(e)}")
                return None
        else:
            return self.place_order(side, amount)