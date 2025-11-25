# executor_fixed.py - VERSIÓN CORREGIDA Y COMPLETA
import ccxt
import logging
import time
import pandas as pd
from config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE, TRADING_MODE, LEVERAGE

class TradeExecutor:
    def __init__(self, symbol):
        self.symbol = symbol
        self.exchange = None
        self._init_exchange()
        logging.info(f"💱 Ejecutor inicializado para {symbol} en modo {TRADING_MODE}")

    def _normalize_symbol(self, symbol):
        """Convierte símbolo al formato Binance API"""
        normalized = symbol.replace("/", "").replace(":", "").replace("-", "").upper()
        return normalized

    def _init_exchange(self):
        if MODE == "live":
            exchange_config = {
                'apiKey': BINANCE_API_KEY,
                'secret': BINANCE_API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'adjustForTimeDifference': True,
                    'defaultType': 'future' if TRADING_MODE == "futures" else 'spot',
                    'warnOnFetchOpenOrdersWithoutSymbol': False  # Suprimir warning
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

    def _set_leverage(self):
        if MODE != "live" or TRADING_MODE != "futures" or not self.exchange:
            return
        
        try:
            symbol = self._normalize_symbol(self.symbol)
            market = self.exchange.market(symbol)
            symbol_id = market['id']
            self.exchange.set_leverage(LEVERAGE, symbol_id)
            logging.info(f"⚙️ Apalancamiento configurado a {LEVERAGE}x para {self.symbol}")
        except Exception as e:
            logging.warning(f"⚠️ No se pudo establecer apalancamiento: {str(e)}")

    def cancel_all_associated_orders(self, symbol):
        """Cancela TODAS las órdenes asociadas a un símbolo"""
        try:
            binance_symbol = self._normalize_symbol(symbol)
            logging.info(f"🔍 Buscando ÓRDENES ABIERTAS para {binance_symbol}...")
            
            open_orders = []
            try:
                open_orders = self.exchange.fetch_open_orders(binance_symbol)
            except Exception as e:
                logging.warning(f"⚠️ Error al obtener órdenes: {str(e)}. Intentando método alternativo...")
                if hasattr(self.exchange, 'fapiPrivateGetOpenOrders'):
                    params = {'symbol': binance_symbol}
                    result = self.exchange.fapiPrivateGetOpenOrders(params)
                    open_orders = result.get('orders', [])
            
            canceled_count = 0
            for order in open_orders:
                try:
                    order_id = order.get('id', order.get('orderId'))
                    if order_id:
                        self.exchange.cancel_order(order_id, binance_symbol)
                        canceled_count += 1
                        
                        order_type = order.get('type', 'N/A')
                        stop_price = order.get('stopPrice', 'N/A')
                        price = order.get('price', 'N/A')
                        logging.info(f"✅ Orden cancelada | ID: {order_id} | Tipo: {order_type} | Stop: {stop_price} | Precio: {price}")
                except Exception as e:
                    logging.warning(f"⚠️ Error cancelando orden {order.get('id', 'N/A')}: {str(e)}")
            
            logging.info(f"✅ TOTAL ÓRDENES CANCELADAS para {binance_symbol}: {canceled_count}")
            return canceled_count
            
        except Exception as e:
            logging.error(f"❌ ERROR CRÍTICO EN LIMPIEZA DE ÓRDENES: {str(e)}")
            return 0

    def place_order(self, side, amount, price=None, sl_price=None, tp_price=None):
        if MODE == "paper":
            order_type = "MARKET"
            if sl_price and tp_price:
                order_type = "OCO (simulado)"
            print(f"[PAPER] {side.upper()} {amount:.6f} de {self.symbol} | Tipo: {order_type}")
            return {"status": "filled", "price": price or 60000, "amount": amount}
        else:
            try:
                logging.info(f"🚀 ENVIANDO ORDEN A BINANCE | {side.upper()} {amount:.6f} {self.symbol}")
                logging.info(f"  📊 SL: {sl_price} | TP: {tp_price} | Modo: {TRADING_MODE}")
                
                server_time = self.exchange.fetch_time()
                logging.info(f"  ⏱️ Binance server time: {pd.Timestamp(server_time, unit='ms')}")
                
                balance = self.exchange.fetch_balance()
                usdt_balance = balance.get('USDT', {}).get('total', 0)
                logging.info(f"  💰 Saldo USDT disponible: ${usdt_balance:.2f}")
                
                if TRADING_MODE == "futures":
                    self._set_leverage()
                    binance_symbol = self._normalize_symbol(self.symbol)
                    
                    # Abrir posición
                    market_order = self.exchange.create_order(
                        symbol=binance_symbol,
                        type='MARKET',
                        side=side.upper(),
                        amount=amount
                    )
                    logging.info(f"✅ POSICIÓN ABIERTA | ID: {market_order.get('id', 'N/A')}")
                    
                    order_ids = []
                    # Stop Loss
                    if sl_price is not None:
                        sl_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        sl_order = self.exchange.create_order(
                            symbol=binance_symbol,
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
                        logging.info(f"🛑 Stop Loss creado | ID: {sl_order.get('id', 'N/A')} @ {sl_price}")
                        order_ids.append(sl_order.get('id', ''))
                    
                    # Take Profit
                    if tp_price is not None:
                        tp_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        tp_order = self.exchange.create_order(
                            symbol=binance_symbol,
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
                        logging.info(f"🎯 Take Profit creado | ID: {tp_order.get('id', 'N/A')} @ {tp_price}")
                        order_ids.append(tp_order.get('id', ''))
                    
                    return {
                        'market_order': market_order,
                        'sl_order_id': order_ids[0] if order_ids else None,
                        'tp_order_id': order_ids[1] if len(order_ids) > 1 else None
                    }
                
                return None
                
            except Exception as e:
                error_msg = f"❌ ERROR AL ENVIAR ORDEN: {str(e)}"
                logging.error(error_msg)
                
                if "code" in str(e):
                    code = str(e).split("code")[1].split(",")[0] if "code" in str(e) else "N/A"
                    logging.error(f"  🔍 Código de error Binance: {code}")
                
                try:
                    from notifier import send_telegram_message
                    send_telegram_message(f"🚨 ERROR CRÍTICO\n{error_msg}\n{self.symbol}")
                except:
                    pass
                
                return None

    def get_account_balance(self):
        try:
            if TRADING_MODE == "futures":
                balance = self.exchange.fetch_balance()
                return float(balance.get('USDT', {}).get('total', 0.0))
            else:
                balance = self.exchange.fetch_balance()
                return float(balance.get('USDT', {}).get('free', 0.0))
        except Exception as e:
            logging.error(f"❌ Error al obtener balance: {str(e)}")
            return 0.0