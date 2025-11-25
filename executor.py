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
                usdt_balance = balance.get('USDT', {}).get('total', 0.0)
                return float(usdt_balance)
            else:
                # Para spot
                balance = self.exchange.fetch_balance()
                usdt_balance = balance.get('USDT', {}).get('free', 0.0)
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
            positions = self.exchange.fetch_positions([symbol] if symbol else None)
            return [p for p in positions if float(p['contracts']) > 0]
        except Exception as e:
            logging.warning(f"⚠️ Error al obtener posiciones: {str(e)}")
            return []

    def cancel_all_associated_orders(self, symbol):
        """Cancela TODAS las órdenes asociadas a un símbolo (SL/TP y órdenes pendientes)"""
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            logging.info(f"🔍 Buscando ÓRDENES ABIERTAS para {normalized_symbol}...")
            
            open_orders = []
            try:
                # ✅ MÉTODO CORRECTO EN CCXT
                open_orders = self.exchange.fetch_open_orders(normalized_symbol)
            except Exception as e:
                logging.warning(f"⚠️ Error al obtener órdenes: {str(e)}. Intentando método alternativo...")
                # No hay método alternativo necesario en ccxt
            
            canceled_count = 0
            for order in open_orders:
                try:
                    order_id = order.get('id', order.get('orderId'))
                    if order_id:
                        self.exchange.cancel_order(order_id, normalized_symbol)
                        canceled_count += 1
                        
                        order_type = order.get('type', 'N/A')
                        stop_price = order.get('stopPrice', 'N/A')
                        price = order.get('price', 'N/A')
                        logging.info(f"✅ Orden cancelada | ID: {order_id} | Tipo: {order_type} | Stop: {stop_price} | Precio: {price}")
                except Exception as e:
                    logging.warning(f"⚠️ Error cancelando orden {order.get('id', 'N/A')}: {str(e)}")
            
            logging.info(f"✅ TOTAL ÓRDENES CANCELADAS para {normalized_symbol}: {canceled_count}")
            return canceled_count
            
        except Exception as e:
            logging.error(f"❌ ERROR CRÍTICO EN LIMPIEZA DE ÓRDENES: {str(e)}")
            return 0

    def place_order(self, side, amount, price=None, sl_price=None, tp_price=None):
        """
        Ejecuta órdenes en Binance USD-M Futures
        """
        if MODE == "paper":
            # Modo paper: solo imprimir
            order_type = "MARKET"
            if sl_price and tp_price:
                order_type = "OCO (simulado)"
            print(f"[PAPER] {side.upper()} {amount:.6f} de {self.symbol} | Tipo: {order_type}")
            if sl_price and tp_price:
                print(f"  📌 SL: {sl_price:.2f} | TP: {tp_price:.2f} (simulados)")
            return {"status": "filled", "price": price or 60000, "amount": amount}
        
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
                    logging.info(f"✅ Posición abierta: {side.upper()} {amount:.6f} de {normalized_symbol} | ID: {market_order.get('id', 'N/A')}")
                    
                    # 2. Crear órdenes SL/TP por separado
                    order_ids = []
                    
                    if sl_price is not None:
                        sl_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        logging.info(f"🛑 Creando Stop Loss: {sl_side} {amount} @ {sl_price}")
                        sl_order = self.exchange.create_order(
                            symbol=normalized_symbol,
                            type='STOP_MARKET',
                            side=sl_side,
                            amount=amount,
                            params={
                                'stopPrice': sl_price,
                                'closePosition': True,
                                'workingType': 'CONTRACT_PRICE',
                                'priceProtect': True
                            }
                        )
                        logging.info(f"🛑 Stop Loss creado | ID: {sl_order.get('id', 'N/A')} | Precio: {sl_price:.2f}")
                        order_ids.append(sl_order.get('id', ''))
                    
                    if tp_price is not None:
                        tp_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        logging.info(f"🎯 Creando Take Profit: {tp_side} {amount} @ {tp_price}")
                        tp_order = self.exchange.create_order(
                            symbol=normalized_symbol,
                            type='TAKE_PROFIT_MARKET',
                            side=tp_side,
                            amount=amount,
                            params={
                                'stopPrice': tp_price,
                                'closePosition': True,
                                'workingType': 'CONTRACT_PRICE',
                                'priceProtect': True
                            }
                        )
                        logging.info(f"🎯 Take Profit creado | ID: {tp_order.get('id', 'N/A')} | Precio: {tp_price:.2f}")
                        order_ids.append(tp_order.get('id', ''))
                    
                    return {
                        'market_order': market_order,
                        'sl_order_id': order_ids[0] if order_ids else None,
                        'tp_order_id': order_ids[1] if len(order_ids) > 1 else None
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

    def close_position(self, amount, side="sell"):
        """Cierra posición (usado principalmente en modo paper)"""
        if MODE == "paper":
            print(f"[PAPER] CIERRE {side.upper()} {amount:.6f} de {self.symbol}")
            return {"status": "filled"}
        
        if TRADING_MODE == "futures":
            try:
                normalized_symbol = self._normalize_symbol(self.symbol)
                order = self.exchange.create_order(
                    symbol=normalized_symbol,
                    type='MARKET',
                    side=side.upper(),
                    amount=amount,
                    params={'reduceOnly': True}
                )
                logging.info(f"✅ Posición cerrada manualmente: {side.upper()} {amount:.6f} | ID: {order.get('id', 'N/A')}")
                return order
            except Exception as e:
                logging.error(f"❌ Error al cerrar posición: {str(e)}")
                return None
        else:
            return self.place_order(side, amount)