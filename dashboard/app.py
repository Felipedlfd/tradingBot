import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path

TRADES_FILE = Path("../trades.json")

def load_trades():
    if TRADES_FILE.exists():
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

st.set_page_config(page_title="Crypto Agent Dashboard", layout="wide")
st.title("🚀 Crypto Trading Agent - Dashboard")

trades = load_trades()
if trades:
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp', ascending=False)
    df['cum_pnl'] = df['pnl'].cumsum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Trades", len(df))
    col2.metric("Ganancia Total", f"${df['pnl'].sum():.2f}")
    col3.metric("Win Rate", f"{(df['pnl'] > 0).mean() * 100:.1f}%")

    st.subheader("Últimos Trades")
    st.dataframe(df[['type', 'price', 'exit_price', 'pnl', 'reason', 'timestamp']].head(20))

    st.subheader("Curva de Capital")
    st.line_chart(df.set_index('timestamp')['cum_pnl'])
else:
    st.info("No hay trades aún. ¡El agente está trabajando!")

st.rerun()