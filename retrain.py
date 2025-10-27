"""
Script para reentrenar manualmente la estrategia del agente.
Ejecuta: venv\\Scripts\\python retrain.py
"""

import sys
from pathlib import Path

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent))

from config import SYMBOL, TRADING_MODE
from learner import optimize_parameters

def main():
    print("🧠 Iniciando reentrenamiento manual...")
    print(f"Modo: {TRADING_MODE} | Símbolo base: {SYMBOL}")
    
    # Ajustar símbolo para futuros
    symbol_to_use = "BTC/USDT:USDT" if TRADING_MODE == "futures" else SYMBOL
    
    try:
        # Reentrenar con últimos 7 días de datos
        best_params = optimize_parameters(
            symbol=symbol_to_use,
            trading_mode=TRADING_MODE,
            days=7  # puedes cambiar a 3, 14, etc.
        )
        print("\n✅ ¡Reentrenamiento completado con éxito!")
        print("Los nuevos parámetros se usarán en la próxima ejecución del agente.")
        
    except KeyboardInterrupt:
        print("\n⚠️ Reentrenamiento cancelado por el usuario.")
    except Exception as e:
        print(f"\n❌ Error durante el reentrenamiento: {e}")
        print("El agente seguirá usando los parámetros anteriores.")

if __name__ == "__main__":
    main()