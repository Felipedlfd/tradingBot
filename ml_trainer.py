# ml_trainer.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
from data import fetch_ohlcv
from indicators import add_indicators

def create_features_and_labels(df, lookahead=10, threshold=0.02):
    """
    Crea features (X) y etiquetas (y) para entrenamiento.
    - lookahead: cuántas velas mirar al futuro.
    - threshold: % mínimo de ganancia para etiquetar como "compra".
    """
    df = df.copy()
    
    # Calcular retorno futuro
    df['future_close'] = df['close'].shift(-lookahead)
    df['future_return'] = (df['future_close'] - df['close']) / df['close']
    
    # Etiquetas: 1 = compra, 0 = no operar, -1 = short (opcional)
    df['label'] = 0
    df.loc[df['future_return'] > threshold, 'label'] = 1    # Long
    df.loc[df['future_return'] < -threshold, 'label'] = -1  # Short
    
    # Eliminar filas con NaN
    df = df.dropna()
    
    # Features: todos los indicadores + liquidez
    feature_cols = [
        'open', 'high', 'low', 'close', 'volume',
        'ema50', 'ema200', 'rsi', 'atr',
        'upper_wick', 'lower_wick', 'body',
        'liquidez'  # ← ¡tu nuevo indicador!
    ]
    
    X = df[feature_cols]
    y = df['label']
    
    return X, y, feature_cols

# ... (todo igual hasta create_features_and_labels) ...

def train_ml_model(symbol="BTC/USDT:USDT", days=30):
    print("📥 Descargando datos históricos...")
    df_hist = fetch_ohlcv(symbol, "1h", limit=24*days)
    df_hist = add_indicators(df_hist)
    
    # Añadir liquidez si no existe
    if 'liquidez' not in df_hist.columns:
        df_hist['spread'] = (df_hist['high'] - df_hist['low']) / df_hist['close']
        df_hist['liquidez'] = df_hist['volume'] / (df_hist['spread'] + 1e-8)
    
    print("⚙️  Creando features históricos...")
    X_hist, y_hist, feature_cols = create_features_and_labels(
        df_hist, lookahead=10, threshold=0.015
    )
    
    # ✅ PASO CLAVE: Cargar trades reales como datos adicionales
    from utils_ml import load_real_trades_as_labels
    df_real = load_real_trades_as_labels(symbol=symbol, min_pnl_abs=1.0)
    
    X_real = pd.DataFrame()
    y_real = pd.Series(dtype='int')
    
    if not df_real.empty:
        print(f"➕ Añadiendo {len(df_real)} trades reales al entrenamiento...")
        # Para cada trade real, extraer las features en ese timestamp
        X_real_list = []
        y_real_list = []
        
        for _, trade in df_real.iterrows():
            # Buscar la vela más cercana al timestamp del trade
            closest_idx = df_hist.index.get_indexer([trade['timestamp']], method='nearest')
            if closest_idx[0] >= 0 and closest_idx[0] < len(df_hist):
                features = df_hist[feature_cols].iloc[closest_idx[0]]
                X_real_list.append(features)
                y_real_list.append(trade['label'])
        
        if X_real_list:
            X_real = pd.DataFrame(X_real_list)
            y_real = pd.Series(y_real_list)
    
    # Combinar datos históricos + reales
    if not X_real.empty:
        X = pd.concat([X_hist, X_real], ignore_index=True)
        y = pd.concat([y_hist, y_real], ignore_index=True)
        print(f"📊 Datos combinados: {len(X)} muestras ({len(X_hist)} históricas + {len(X_real)} reales)")
    else:
        X, y = X_hist, y_hist
        print(f"📊 Solo datos históricos: {len(X)} muestras")
    
    if len(X) < 100:
        print("❌ Pocos datos para entrenar.")
        return
    
    # ... (resto igual: división, entrenamiento, guardado) ...
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight='balanced'
    )
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    print("\n✅ Resultados del modelo:")
    print(classification_report(y_test, y_pred, target_names=['Short', 'Esperar', 'Long']))
    
    joblib.dump(model, 'ml_model.pkl')
    joblib.dump(feature_cols, 'feature_cols.pkl')
    print("\n💾 Modelo guardado como 'ml_model.pkl'")

if __name__ == "__main__":
    from config import SYMBOL, TRADING_MODE
    symbol_to_use = "BTC/USDT:USDT" if TRADING_MODE == "futures" else SYMBOL
    train_ml_model(symbol=symbol_to_use, days=60)