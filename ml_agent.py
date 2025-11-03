import logging
import pandas as pd
try:
    import joblib
    MODEL = joblib.load('ml_model.pkl')
    FEATURE_COLS = joblib.load('feature_cols.pkl')
    ML_READY = True
except FileNotFoundError:
    logging.warning("❌ Modelo ML no encontrado. Ejecuta 'ml_trainer.py' primero.")
    MODEL = None
    FEATURE_COLS = []
    ML_READY = False

class MLAgent:
    def __init__(self):
        self.model = MODEL
        self.feature_cols = FEATURE_COLS
        self.ml_ready = ML_READY
        if self.ml_ready:
            logging.info("🤖 Modelo ML cargado exitosamente.")
        else:
            logging.warning("⚠️  Modelo ML no disponible.")

    def get_signal(self, symbol, timeframe="1h"):
        """Obsoleto: usa get_signal_from_dataframe en su lugar"""
        if not self.ml_ready:
            return "wait"
        # ... código antiguo (puedes eliminarlo si usas solo get_signal_from_dataframe)

    def get_signal_from_dataframe(self, df):
        """Genera señal a partir de un DataFrame preprocesado"""
        if not self.ml_ready or df.empty:
            return 'wait'
        
        try:
            # Asegurar que todas las features existan
            if 'liquidez' not in df.columns:
                df['spread'] = (df['high'] - df['low']) / df['close']
                df['liquidez'] = df['volume'] / (df['spread'] + 1e-8)
            
            last_row = df[self.feature_cols].iloc[-1:].copy()
            pred = self.model.predict(last_row)[0]
            proba = self.model.predict_proba(last_row)[0]
            confidence = max(proba)
            
            if confidence < 0.5:
                return 'wait'
            return 'long' if pred == 1 else 'short' if pred == -1 else 'wait'
        except Exception as e:
            logging.error(f"Error en ML: {e}")
            return 'wait'