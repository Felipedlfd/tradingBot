# utils_ml.py
import pandas as pd
import json
from pathlib import Path

def load_real_trades_as_labels(symbol="BTC/USDT:USDT", min_pnl_abs=0):
    """
    Usa real_trades.json (filtrado) en vez de trades.json.
    """
    trades_file = Path("real_trades.json")  # ← ¡cambio clave!
    if not trades_file.exists():
        return pd.DataFrame()
    
    with open(trades_file, "r") as f:
        trades = json.load(f)
    
    filtered = []
    for t in trades:
        if 'pnl' not in t or t.get('symbol', symbol) != symbol:
            continue
        if abs(t['pnl']) < min_pnl_abs:
            continue
        filtered.append(t)
    
    if not filtered:
        return pd.DataFrame()
    
    df_trades = pd.DataFrame(filtered)
    df_trades['label'] = df_trades['pnl'].apply(lambda x: 1 if x > 0 else -1)
    df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])
    
    return df_trades[['timestamp', 'label']]