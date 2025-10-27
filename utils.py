# utils.py (actualizado)
import json
import os
from pathlib import Path
from config import MODE

TRADES_FILE = Path("trades.json")

def save_trade(trade_dict):
    # Añadir fuente automáticamente
    trade_dict["source"] = "live" if MODE == "live" else "paper"
    
    if TRADES_FILE.exists():
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            trades = json.load(f)
    else:
        trades = []
    trades.append(trade_dict)
    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, default=str)