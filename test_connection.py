# test_connection.py
from executor import TradeExecutor
from config import SYMBOL
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_live_connection():
    print("🔍 PRUEBA DE CONEXIÓN EN MODO LIVE")
    print("=" * 50)
    
    try:
        # Crear ejecutor
        executor = TradeExecutor(SYMBOL)
        
        # Obtener balance de futuros
        print("\n💰 BALANCE DE CUENTA:")
        balance = executor.exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('total', 0)
        print(f"  USDT disponible: ${usdt_balance:.2f}")
        
        # Obtener posiciones abiertas
        print("\n📊 POSICIONES ABIERTAS:")
        positions = executor.get_positions()
        if not positions:
            print("  No hay posiciones abiertas")
        for pos in positions:
            print(f"  {pos['symbol']}: {pos['contracts']} contratos")
        
        # Verificar apalancamiento
        print("\n⚙️ APALANCAMIENTO ACTUAL:")
        try:
            market = executor.exchange.market(executor.symbol)
            symbol_id = market['id']
            account_info = executor.exchange.fetch_account_info()
            for asset in account_info['positions']:
                if asset['symbol'] == symbol_id:
                    print(f"  {executor.symbol}: {asset['leverage']}x")
        except Exception as e:
            print(f"  ❌ Error al verificar apalancamiento: {str(e)}")
        
        print("\n✅ ¡Conexión exitosa! Puedes proceder a pruebas con órdenes.")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR DE CONEXIÓN: {str(e)}")
        print("ℹ️ Posibles soluciones:")
        print("  - Verifica tus API keys en .env")
        print("  - Asegúrate de tener IP Whitelist en Binance")
        print("  - Confirma que el símbolo es correcto (BTCUSDT)")
        return False

if __name__ == "__main__":
    test_live_connection()