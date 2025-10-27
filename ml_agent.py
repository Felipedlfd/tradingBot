# ml_agent.py
import joblib
import pandas as pd
from data import fetch_ohlcv
from indicators import add_indicators

class MLAgent:
    def __init__(self):
        try:
            self.model = joblib.load('ml_model.pkl')
            self.feature_cols = joblib.load('feature_cols.pkl')
            print("🤖 Modelo ML cargado exitosamente.")
        except FileNotFoundError:
            print("❌ Modelo no encontrado. Ejecuta 'ml_trainer.py' primero.")
            self.model = None

    def get_signal(self, symbol, timeframe="1h"):
        if self.model is None:
            return "wait"
        
        # Obtener últimos datos
        df = fetch_ohlcv(symbol, timeframe, limit=300)
        df = add_indicators(df)
        
        # Si no hay liquidez, calcularla
        if 'liquidez' not in df.columns:
            df['spread'] = (df['high'] - df['low']) / df['close']
            df['liquidez'] = df['volume'] / (df['spread'] + 1e-8)
        
        # Tomar la última vela
        last_row = df[self.feature_cols].iloc[-1:].copy()
        
        # Predecir
        pred = self.model.predict(last_row)[0]
        proba = self.model.predict_proba(last_row)[0]
        confidence = max(proba)
        
        if confidence < 0.6:  # umbral de confianza
            return "wait"
        
        return "long" if pred == 1 else "short" if pred == -1 else "wait"