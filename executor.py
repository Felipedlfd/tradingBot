# executor.py
import ccxt
import logging
from config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE, TRADING_MODE, LEVERAGE

class TradeExecutor:
    def __init__(self, symbol):
        # ✅ SOLUCIÓN 1: Convertir símbolo al formato correcto de Binance API
        self.symbol = self._normalize_symbol(symbol)
        self.exchange = None
        self._init_exchange()
        logging.info(f"💱 Ejecutor inicializado para {self.symbol} en modo {TRADING_MODE}")

    def get_account_balance(self):
        """Obtiene el saldo real disponible en USDT (preciso para futures)"""
        try:
            if TRADING_MODE == "futures":
                logging.debug("🔍 Obteniendo balance de USD-M Futures...")
                balance = self.exchange.fetch_balance()
                
                logging.debug(f"📊 Balance completo: {balance}")
                
                # Método 1: Buscar USDT directamente
                if 'USDT' in balance and isinstance(balance['USDT'], dict):
                    usdt_balance = float(balance['USDT'].get('total', 0.0))
                    logging.info(f"✅ Balance USDT obtenido: ${usdt_balance:.2f}")
                    return usdt_balance
                
                # Método 2: Buscar en info
                if hasattr(balance, 'info'):
                    info = balance.info
                    if isinstance(info, dict):
                        assets = info.get('assets', [])
                        for asset in assets:
                            if isinstance(asset, dict) and asset.get('asset') == 'USDT':
                                wallet_balance = float(asset.get('walletBalance', 0.0))
                                logging.info(f"✅ Balance wallet USDT: ${wallet_balance:.2f}")
                                return wallet_balance
                
                logging.warning("⚠️ No se encontró balance USDT en la respuesta")
                return 0.0
                
            else:
                # Para spot
                balance = self.exchange.fetch_balance()
                return float(balance.get('USDT', {}).get('free', 0.0))
                
        except Exception as e:
            logging.error(f"❌ Error al obtener balance: {str(e)}")
            try:
                # Fallback simple
                balance = self.exchange.fetch_balance()
                return float(balance.get('USDT', {}).get('total', 0.0))
            except Exception as fallback_e:
                logging.error(f"❌ Fallback también falló: {str(fallback_e)}")
                return 0.0
    
    def _normalize_symbol(self, symbol):
        """
        Convierte el símbolo al formato correcto para ccxt con Binance USD-M Futures
        Ejemplos:
        - "BTC/USDT" → "BTC/USDT:USDT"
        - "BTCUSDT" → "BTC/USDT:USDT"
        - "BTC/USDT:USDT" → "BTC/USDT:USDT" (ya correcto)
        """
        # Eliminar espacios y convertir a mayúsculas
        symbol_clean = symbol.strip().upper()
        
        # Caso 1: Ya tiene el formato correcto
        if symbol_clean.endswith(":USDT") and "/" in symbol_clean:
            normalized = symbol_clean
        # Caso 2: Tiene slash pero no :USDT (ej: "BTC/USDT")
        elif "/" in symbol_clean and not symbol_clean.endswith(":USDT"):
            base, quote = symbol_clean.split("/")
            normalized = f"{base}/{quote}:USDT"
        # Caso 3: Sin slash (ej: "BTCUSDT")
        else:
            # Extraer base (BTC) y quote (USDT)
            if symbol_clean.startswith("BTC"):
                base = "BTC"
                quote = "USDT"
            elif symbol_clean.startswith("ETH"):
                base = "ETH"
                quote = "USDT"
            else:
                # Intentar separar por primera aparición de USDT
                if "USDT" in symbol_clean:
                    base = symbol_clean.replace("USDT", "")
                    quote = "USDT"
                else:
                    base = symbol_clean[:3]
                    quote = symbol_clean[3:]
            
            normalized = f"{base}/{quote}:USDT"
        
        logging.info(f"🔄 Normalizando símbolo: '{symbol}' → '{normalized}'")
        return normalized

    def _init_exchange(self):
        """Inicializa la conexión con Binance y carga los mercados"""
        if MODE == "live":
            exchange_config = {
                'apiKey': BINANCE_API_KEY,
                'secret': BINANCE_API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'adjustForTimeDifference': True,
                    'defaultType': 'future' if TRADING_MODE == "futures" else 'spot'
                }
            }
            
            if TRADING_MODE == "futures":
                self.exchange = ccxt.binanceusdm(exchange_config)
                logging.info("🚀 Conectado a Binance USD-M Futures")
            else:
                self.exchange = ccxt.binance(exchange_config)
                logging.info("🚀 Conectado a Binance Spot")
            
            # Cargar mercados
            try:
                self.exchange.load_markets()
                logging.info("✅ Mercados cargados correctamente")
                
                # ✅ SOLUCIÓN 2: Verificar que el símbolo existe en los mercados
                if self.symbol not in self.exchange.markets:
                    logging.warning(f"⚠️ Símbolo {self.symbol} no encontrado en mercados")
                    # Listar algunos símbolos similares
                    similar_symbols = [s for s in self.exchange.symbols if self.symbol[:3] in s]
                    logging.info(f"Símbolos similares disponibles: {similar_symbols[:5]}")
            except Exception as e:
                logging.warning(f"⚠️ Error al cargar mercados: {str(e)}")
        else:
            logging.info("🎭 Modo PAPER: Sin conexión real a Binance")

    def _set_leverage(self):
        """Configura el apalancamiento para futures (solo en modo live)"""
        if MODE != "live" or TRADING_MODE != "futures" or not self.exchange:
            return
        
        try:
            # ✅ SOLUCIÓN 3: Usar el símbolo normalizado
            market = self.exchange.market(self.symbol)
            symbol_id = market['id']  # Devuelve "BTCUSDT"
            
            # Verificar que el símbolo soporta apalancamiento
            if 'leverage' not in market['info']:
                logging.warning(f"⚠️ El símbolo {self.symbol} no soporta apalancamiento")
                return
            
            # Configurar apalancamiento
            self.exchange.set_leverage(LEVERAGE, symbol_id)
            logging.info(f"⚙️ Apalancamiento configurado a {LEVERAGE}x para {self.symbol}")
        except Exception as e:
            logging.warning(f"⚠️ No se pudo establecer apalancamiento: {str(e)}")
            logging.warning("ℹ️ Continuando sin cambiar apalancamiento. Verifica en Binance Web.")

    def place_order(self, side, amount, price=None, sl_price=None, tp_price=None):
        """
        Ejecuta órdenes en Binance USD-M Futures usando la API oficial
        Documentación: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api
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
                    # ✅ SOLUCIÓN 4: Usar el formato de símbolo correcto en todas las llamadas
                    symbol = self.symbol  # Ya normalizado a "BTCUSDT"
                    
                    # 1. Abrir posición con orden de mercado
                    logging.info(f"🔵 Abriendo posición MARKET: {side.upper()} {amount} {symbol}")
                    market_order = self.exchange.create_order(
                        symbol=symbol,
                        type='MARKET',
                        side=side.upper(),
                        amount=amount
                    )
                    logging.info(f"✅ Posición abierta: {side.upper()} {amount:.6f} de {symbol} | ID: {market_order['id']}")
                    
                    # 2. Crear órdenes SL/TP por separado
                    order_ids = []
                    
                    if sl_price is not None:
                        # ✅ SOLUCIÓN 5: Usar STOP_MARKET con closePosition=True
                        sl_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        logging.info(f"🛑 Creando Stop Loss: {sl_side} {amount} @ {sl_price}")
                        sl_order = self.exchange.create_order(
                            symbol=symbol,
                            type='STOP_MARKET',
                            side=sl_side,
                            amount=amount,
                            params={
                                'stopPrice': sl_price,
                                'closePosition': True,  # Cierra toda la posición
                                'workingType': 'CONTRACT_PRICE',
                                'priceProtect': True  # Protección contra slippage extremo
                            }
                        )
                        logging.info(f"🛑 Stop Loss creado | ID: {sl_order['id']} | Precio: {sl_price:.2f}")
                        order_ids.append(sl_order['id'])
                    
                    if tp_price is not None:
                        # ✅ SOLUCIÓN 6: Usar TAKE_PROFIT_MARKET con closePosition=True
                        tp_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
                        logging.info(f"🎯 Creando Take Profit: {tp_side} {amount} @ {tp_price}")
                        tp_order = self.exchange.create_order(
                            symbol=symbol,
                            type='TAKE_PROFIT_MARKET',
                            side=tp_side,
                            amount=amount,
                            params={
                                'stopPrice': tp_price,
                                'closePosition': True,  # Cierra toda la posición
                                'workingType': 'CONTRACT_PRICE',
                                'priceProtect': True  # Protección contra slippage extremo
                            }
                        )
                        logging.info(f"🎯 Take Profit creado | ID: {tp_order['id']} | Precio: {tp_price:.2f}")
                        order_ids.append(tp_order['id'])
                    
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
                
                # ✅ SOLUCIÓN 7: Diagnóstico específico basado en errores comunes
                if "symbol" in str(e).lower():
                    logging.error("🔍 DIAGNÓSTICO: El formato del símbolo es incorrecto")
                    logging.error("💡 SOLUCIÓN: Usa el formato Binance API: 'BTCUSDT' (sin slash)")
                    logging.error(f"  Tu símbolo actual: '{self.symbol}'")
                    logging.error("  Ejemplos correctos: 'BTCUSDT', 'ETHUSDT', 'BNBUSDT'")
                
                if "1013" in str(e):  # Código de error de Binance para símbolo inválido
                    logging.error("🔍 DIAGNÓSTICO: Binance no reconoce el símbolo")
                    logging.error("💡 SOLUCIÓN: Verifica el símbolo en la documentación oficial")
                    logging.error("  https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api")
                
                if "400" in str(e):
                    logging.error("🔍 DIAGNÓSTICO: Parámetros incorrectos en la orden")
                    logging.error("💡 SOLUCIÓN: Verifica que sl_price y tp_price sean números válidos")
                    logging.error(f"  SL: {sl_price}, TP: {tp_price}")
                
                try:
                    from notifier import send_telegram_message
                    send_telegram_message(f"🚨 ERROR EN ORDEN\n{error_msg}\n{self.symbol}")
                except:
                    pass
                
                return None

    def close_position(self, amount, side="sell"):
        """Cierra posición con manejo de errores robusto"""
        if MODE == "paper":
            print(f"[PAPER] CIERRE {side.upper()} {amount:.6f} de {self.symbol}")
            return {"status": "filled"}
        
        if TRADING_MODE == "futures":
            try:
                # ✅ SOLUCIÓN: Verificar posición antes de cerrar
                positions = self.exchange.fetch_positions([self.symbol])
                open_positions = [p for p in positions if float(p['contracts']) > 0]
                
                if not open_positions:
                    logging.warning("ℹ️ Posición ya cerrada. Sin acción necesaria.")
                    return {"status": "already_closed"}
                
                # Cancelar órdenes asociadas primero
                self.cancel_associated_orders(self.symbol)
                
                # Cerrar posición con manejo de reduceOnly
                logging.info(f"CloseOperation: {side.upper()} {amount:.6f} de {self.symbol}")
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='MARKET',
                    side=side.upper(),
                    amount=amount,
                    params={
                        'reduceOnly': True,
                        'newOrderRespType': 'RESULT'
                    }
                )
                logging.info(f"✅ Posición cerrada | ID: {order['id']} | Ejecutado: {order['executedQty']}")
                return order
                
            except Exception as e:
                error_str = str(e)
                
                # ✅ SOLUCIÓN: Manejar error específico de ReduceOnly
                if "-2022" in error_str or "ReduceOnly Order is rejected" in error_str:
                    logging.warning("⚠️ ReduceOnly rechazado (posición ya cerrada). Verificando estado actual...")
                    # Verificar estado actual y sincronizar
                    self._check_position_status()  # Llamar al método de verificación
                    return {"status": "already_closed"}
                
                logging.error(f"❌ Error al cerrar posición: {error_str}")
                return None
        else:
            return self.place_order(side, amount)

    def get_positions(self):
        """Obtiene posiciones abiertas (solo para futures en modo live)"""
        if MODE != "live" or TRADING_MODE != "futures" or not self.exchange:
            return []
        
        try:
            symbol = self.symbol  # Ya normalizado
            positions = self.exchange.fetch_positions([symbol])
            return [p for p in positions if float(p['contracts']) > 0]
        except Exception as e:
            logging.warning(f"⚠️ Error al obtener posiciones: {str(e)}")
            return []

    def cancel_order(self, order_id):
        """Cancela una orden específica"""
        if MODE != "live" or not self.exchange:
            return None
        
        try:
            symbol = self.symbol
            result = self.exchange.cancel_order(order_id, symbol)
            logging.info(f"🚫 Orden cancelada: {order_id} para {symbol}")
            return result
        except Exception as e:
            logging.warning(f"⚠️ Error al cancelar orden {order_id}: {str(e)}")
            return None
        
    def cancel_associated_orders(self, position_symbol):
        """Cancela todas las órdenes asociadas a un símbolo (SL/TP) - Optimizado para BTC"""
        try:
            # ✅ SOLUCIÓN: Especificar SIEMPRE el símbolo para evitar el warning y ahorrar límite de tasa
            binance_symbol = self._get_binance_symbol(position_symbol)
            
            logging.info(f"🧹 Limpiando órdenes para {binance_symbol}...")
            
            # ✅ Obtener SOLO órdenes del símbolo específico
            open_orders = self.exchange.fetch_open_orders(binance_symbol)
            
            canceled_count = 0
            for order in open_orders:
                # ✅ Filtrar solo órdenes de protección (SL/TP)
                if order['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP', 'TAKE_PROFIT']:
                    try:
                        self.cancel_order(order['id'])
                        canceled_count += 1
                        logging.info(f"✅ Órden cancelada | ID: {order['id']} | Tipo: {order['type']} | Precio: {order.get('stopPrice', 'N/A')}")
                    except Exception as e:
                        logging.warning(f"⚠️ Error cancelando orden {order['id']}: {str(e)}")
            
            logging.info(f"✅ Limpieza completada para {binance_symbol} | Órdenes canceladas: {canceled_count}")
            return canceled_count
            
        except Exception as e:
            logging.error(f"❌ Error crítico en limpieza de órdenes: {str(e)}")
            return 0
        
    def _get_binance_symbol(self, symbol):
        """Convierte el símbolo al formato correcto para Binance API"""
        # Para USD-M Futures, Binance usa formato sin slash y sin :USDT
        if TRADING_MODE == "futures":
            return symbol.replace("/", "").replace(":USDT", "").replace("-", "")
        else:
            # Para spot, usar formato con slash
            return symbol.replace(":USDT", "")