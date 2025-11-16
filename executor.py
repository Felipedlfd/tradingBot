# executor.py
import ccxt
from config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE, TRADING_MODE

class TradeExecutor:
    def __init__(self, symbol):
        self.symbol = symbol
        if MODE == "live":
            if TRADING_MODE == "futures":
                self.exchange = ccxt.binanceusdm({
                    'apiKey': BINANCE_API_KEY,
                    'secret': BINANCE_API_SECRET,
                    'enableRateLimit': True,
                    'options': {
                        'adjustForTimeDifference': True
                    }
                })
            else:
                self.exchange = ccxt.binance({
                    'apiKey': BINANCE_API_KEY,
                    'secret': BINANCE_API_SECRET,
                    'enableRateLimit': True,
                    'options': {
                        'adjustForTimeDifference': True
                    }
                })
        self.position = None

    def place_order(self, side, amount, price=None, sl_price=None, tp_price=None):
        """
        Ejecuta órdenes:
        - En modo paper: solo imprime
        - En modo live + futuros: usa órdenes OCO si se proporcionan sl_price/tp_price
        - En modo live + spot: órdenes simples (spot no soporta OCO nativo)
        """
       
        if MODE == "live" and TRADING_MODE == "futures":
            try:
                # Establecer apalancamiento ANTES de ordenar
                self.exchange.set_leverage(LEVERAGE, self.symbol)
                print(f"⚙️ Apalancamiento configurado a {LEVERAGE}x para {self.symbol}")
            except Exception as e:
                logging.warning(f"⚠️ No se pudo establecer apalancamiento: {e}")
        
        if MODE == "paper":
            print(f"[PAPER] {side.upper()} {amount:.6f} de {self.symbol}")
            return {"status": "filled", "price": price or 60000}
        else:
            try:
                if TRADING_MODE == "futures":
                    # Futuros: soporte OCO
                    if sl_price is not None and tp_price is not None:
                        # Crear orden OCO
                        order = self.exchange.create_order(
                            symbol=self.symbol,
                            type='OCO',
                            side=side.upper(),
                            amount=amount,
                            price=tp_price,          # Take Profit (orden límite)
                            stopPrice=sl_price,      # Stop Loss trigger
                            params={
                                'stopLimitPrice': sl_price,  # Precio límite del SL
                                'stopLimitTimeInForce': 'GTC'
                            }
                        )
                        print(f"✅ Orden OCO LIVE creada: {side.upper()} {amount:.6f} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")
                        return order
                    else:
                        # Sin OCO: orden de mercado simple
                        order = self.exchange.create_market_order(self.symbol, side.upper(), amount)
                        print(f"✅ Orden LIVE simple: {side.upper()} {amount:.6f}")
                        return order
                else:
                    # Spot: órdenes simples (no soporta OCO)
                    order = self.exchange.create_market_order(self.symbol, side.upper(), amount)
                    # Nota: Para spot, deberías implementar SL/TP manualmente (menos seguro)
                    print(f"✅ Orden SPOT LIVE: {side.upper()} {amount:.6f}")
                    return order
            except Exception as e:
                print(f"❌ Error en orden LIVE: {e}")
                return None

    def close_position(self, amount, side="sell"):
        """Cierra posición (usado principalmente en modo paper)"""
        return self.place_order(side, amount)