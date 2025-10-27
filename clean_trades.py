# clean_trades.py (versión segura)
import json
from pathlib import Path

TRADES_FILE = Path("trades.json")

def mark_trades_as_real():
    if not TRADES_FILE.exists():
        print("❌ trades.json no existe.")
        return
    
    # Leer contenido
    content = TRADES_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print("⚠️  trades.json está vacío. Ejecuta un backtest primero.")
        return
    
    try:
        trades = json.loads(content)
    except json.JSONDecodeError:
        print("❌ trades.json está corrupto. Elimínalo y genera uno nuevo.")
        return
    
    if not isinstance(trades, list):
        print("❌ Formato inválido en trades.json.")
        return

    updated = False
    for trade in trades:
        if "source" not in trade:
            trade["source"] = "paper"
            updated = True
    
    if updated:
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2, default=str)
        print(f"✅ {len(trades)} trades marcados como 'paper'.")
    else:
        print("ℹ️  Todos los trades ya están marcados.")

def filter_real_trades_for_ml():
    if not TRADES_FILE.exists():
        print("❌ trades.json no existe.")
        return
    
    content = TRADES_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print("⚠️  trades.json está vacío.")
        return
    
    try:
        trades = json.loads(content)
    except json.JSONDecodeError:
        print("❌ trades.json está corrupto.")
        return

    real_trades = [
        t for t in trades 
        if t.get("source") in ["paper", "live"]
    ]
    
    REAL_TRADES_FILE = Path("real_trades.json")
    with open(REAL_TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(real_trades, f, indent=2, default=str)
    
    print(f"✅ {len(real_trades)} trades reales guardados en 'real_trades.json'.")

if __name__ == "__main__":
    print("1. Marcar trades existentes como 'paper'")
    print("2. Filtrar trades reales para ML")
    choice = input("Elige opción (1/2): ").strip()
    
    if choice == "1":
        mark_trades_as_real()
    elif choice == "2":
        filter_real_trades_for_ml()
    else:
        print("Opción inválida.")