# executor.py
import ccxt
import logging
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
                    'defaultType': 'future' if TRADING_MODE == "futures" else 'spot'
                }
            }
            
            if TRADING_MODE == "futures":
                self.exchange = ccxt.binanceusdm(exchange_config)
                logging.info("🚀 Conectado a Binance USDⓈ-M Futures")
            else:
                self.exchange = ccxt.binance(exchange_config)
                logging.info("🚀 Conectado a Binance Spot")
            
            # 🔑 CARGAR MERCADOS ANTES DE USARLOS (solución al primer error)
            try:
                self.exchange.load_markets()
                logging.info("✅ Mercados cargados correctamente")
            except Exception as e:
                logging.warning(f"⚠️ Error al cargar mercados: {str(e)}")
        else:
            logging.info("🎭 Modo PAPER: Sin conexión real a Binance")

    def _set_leverage(self):
        """Configura el apalancamiento para futures (solo en modo live)"""
        if MODE != "live" or TRADING_MODE != "futures" or not self.exchange:
            return
        
        try:
            # ✅ Asegurar que los mercados están cargados
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                self.exchange.load_markets()
            
            market = self.exchange.market(self.symbol)
            symbol_id = market['id']
            
            # ✅ Verificar que el símbolo existe en futures
            if symbol_id not in self.exchange.markets:
                logging.error(f"❌ Símbolo {symbol_id} no encontrado en mercados de Binance")
                return
            
            # ✅ Configurar apalancamiento
            self.exchange.set_leverage(LEVERAGE, symbol_id)
            logging.info(f"⚙️ Apalancamiento configurado a {LEVERAGE}x para {self.symbol}")
        except Exception as e:
            logging.warning(f"⚠️ No se pudo establecer apalancamiento: {str(e)}")
            logging.warning("ℹ️ Continuando sin cambiar apalancamiento. Verifica en Binance Web.")

    def place_order(self, side, amount, price=None, sl_price=None, tp_price=None):
        """
        Ejecuta órdenes con parámetros correctos para Binance Futures
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
            # Modo live: conectar con Binance
            try:
                if TRADING_MODE == "futures":
                    # ✅ CARGAR MERCADOS SI ES NECESARIO
                    if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                        self.exchange.load_markets()
                    
                    # Configurar apalancamiento primero
                    self._set_leverage()
                    
                    # ✅ SINTAXIS CORRECTA PARA ÓRDENES OCO EN BINANCE FUTURES
                    if sl_price is not None and tp_price is not None:
                        params = {
                            'stopPrice': sl_price,           # Precio de activación del SL
                            'stopLimitPrice': sl_price,      # Precio límite del SL
                            'stopLimitTimeInForce': 'GTC'    # Good Till Cancelled
                        }
                        
                        order = self.exchange.create_order(
                            symbol=self.symbol,
                            type='OCO',
                            side=side.upper(),
                            amount=amount,
                            price=tp_price,                  # Precio del Take Profit
                            params=params
                        )
                        logging.info(f"✅ Orden OCO LIVE creada: {side.upper()} {amount:.6f} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")
                        return order
                    else:
                        # Sin OCO: orden de mercado simple
                        order = self.exchange.create_market_order(self.symbol, side.upper(), amount)
                        logging.info(f"✅ Orden LIVE simple: {side.upper()} {amount:.6f}")
                        return order
                else:
                    # Spot: órdenes simples (no soporta OCO)
                    order = self.exchange.create_market_order(self.symbol, side.upper(), amount)
                    logging.info(f"✅ Orden SPOT LIVE: {side.upper()} {amount:.6f}")
                    return order
            except Exception as e:
                error_msg = f"❌ Error en orden LIVE ({side.upper()} {amount:.6f}): {str(e)}"
                logging.error(error_msg)
                
                # Intentar obtener más información del error
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logging.error(f"Respuesta de Binance: {e.response.text}")
                
                # Mostrar ayuda específica para errores comunes
                if "unexpected keyword argument 'stopPrice'" in str(e):
                    logging.error("🔍 SOLUCIÓN: Usa 'params' con 'stopPrice' para órdenes OCO en Binance Futures")
                
                # Notificar por Telegram en errores críticos
                try:
                    from notifier import send_telegram_message
                    send_telegram_message(f"🚨 ERROR EN ORDEN\n{error_msg}\n{self.symbol}")
                except Exception as telegram_e:
                    logging.warning(f"⚠️ No se pudo enviar notificación por Telegram: {telegram_e}")
                
                return None

    def close_position(self, amount, side="sell"):
        """Cierra posición (usado principalmente en modo paper)"""
        if MODE == "paper":
            print(f"[PAPER] CIERRE {side.upper()} {amount:.6f} de {self.symbol}")
            return {"status": "filled"}
        
        # En modo live, para futures, Binance ya cerró con OCO
        if TRADING_MODE == "futures":
            logging.info("ℹ️ En futures, la posición se cierra automáticamente con OCO")
            return {"status": "closed_by_exchange"}
        else:
            # Para spot, cerramos manualmente
            return self.place_order(side, amount)

    def get_positions(self):
        """Obtiene posiciones abiertas (solo para futures en modo live)"""
        if MODE != "live" or TRADING_MODE != "futures" or not self.exchange:
            return []
        
        try:
            # ✅ Asegurar que los mercados están cargados
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                self.exchange.load_markets()
            
            positions = self.exchange.fetch_positions([self.symbol])
            return [p for p in positions if float(p['contracts']) > 0]
        except Exception as e:
            logging.warning(f"⚠️ Error al obtener posiciones: {str(e)}")
            return []