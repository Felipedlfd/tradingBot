import pandas as pd
import numpy as np
import logging
import joblib
import time
import json
from datetime import datetime
from pathlib import Path
from config import SYMBOL, TRADING_MODE
from data import fetch_ohlcv  # ✅ Solo fetch_ohlcv viene de data.py
from indicators import add_indicators  # ✅ add_indicators viene de indicators.py
from utils_ml import load_real_trades_as_labels
from risk_manager import calculate_position_size
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.utils.class_weight import compute_class_weight

def create_features_and_labels(df, lookahead=10, threshold=0.015):
    """
    Crea features (X) y etiquetas (y) para entrenamiento.
    - lookahead: cuántas velas mirar al futuro.
    - threshold: % mínimo de ganancia para etiquetar como "compra".
    """
    df = df.copy()
    
    # Añadir indicadores técnicos
    df = add_indicators(df)
    
    # Calcular retorno futuro
    df['future_close'] = df['close'].shift(-lookahead)
    df['future_return'] = (df['future_close'] - df['close']) / df['close']
    
    # Etiquetas: 1 = compra (long), 0 = no operar, -1 = venta (short)
    df['label'] = 0
    df.loc[df['future_return'] > threshold, 'label'] = 1    # Long
    df.loc[df['future_return'] < -threshold, 'label'] = -1  # Short
    
    # Eliminar filas con NaN
    df = df.dropna()
    
    # Features: todos los indicadores
    feature_cols = [
        'open', 'high', 'low', 'close', 'volume',
        'ema50', 'ema200', 'rsi', 'atr',
        'upper_wick', 'lower_wick', 'body',
        'liquidez'
    ]
    
    X = df[feature_cols]
    y = df['label']
    
    return X, y, feature_cols

def train_ml_model(symbol="BTC/USDT:USDT", days=30):
    print("📥 Descargando datos históricos...")
    df = fetch_ohlcv(symbol, "1h", limit=24*days)
    
    if df.empty:
        print("❌ Error al cargar datos.")
        return
    
    print("⚙️  Creando features y etiquetas...")
    X, y, feature_cols = create_features_and_labels(df, lookahead=10, threshold=0.015)
    
    # ✅ PASO CLAVE: Cargar trades reales como datos adicionales
    df_real = load_real_trades_as_labels(symbol=symbol, min_pnl_abs=1.0)
    
    X_real = pd.DataFrame()
    y_real = pd.Series(dtype='int')
    
    if not df_real.empty:
        print(f"➕ Añadiendo {len(df_real)} trades reales al entrenamiento...")
        X_real_list = []
        y_real_list = []
        
        for _, trade in df_real.iterrows():
            # Buscar la vela más cercana al timestamp del trade
            closest_idx = df.index.get_indexer([trade['timestamp']], method='nearest')
            if closest_idx[0] >= 0 and closest_idx[0] < len(df):
                features = df[feature_cols].iloc[closest_idx[0]]
                X_real_list.append(features)
                y_real_list.append(trade['label'])
        
        if X_real_list:
            X_real = pd.DataFrame(X_real_list, columns=feature_cols)
            y_real = pd.Series(y_real_list)
    
    # Combinar datos históricos + reales
    if not X_real.empty:
        X = pd.concat([X, X_real], ignore_index=True)
        y = pd.concat([y, y_real], ignore_index=True)
        print(f"📊 Datos combinados: {len(X)} muestras ({len(X)-len(X_real)} históricas + {len(X_real)} reales)")
    else:
        print(f"📊 Solo datos históricos: {len(X)} muestras")
    
    if len(X) < 100:
        print("❌ Pocos datos para entrenar.")
        return
    
    # Dividir en train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # 💡 ✅ BALANCEO DE CLASES: Calcula pesos para clases desbalanceadas
    classes = sorted(set(y_train))
    class_weights = compute_class_weight('balanced', classes=classes, y=y_train)
    class_weight_dict = dict(zip(classes, class_weights))
    print(f"⚖️ Pesos de clases calculados: {class_weight_dict}")
    
    # 💡 ✅ PONDERACIÓN POR IMPACTO: Crear pesos basados en el PnL de trades reales
    sample_weights = np.ones(len(X_train))  # Peso base = 1.0
    
    if not X_real.empty:
        print("📊 Preparando ponderación por impacto de trades...")
        
        # Identificar índices de trades reales en el conjunto de entrenamiento
        real_train_mask = np.isin(range(len(X)), range(len(X)-len(X_real), len(X)))[np.isin(range(len(X)), range(len(X_train)))]
        
        if np.any(real_train_mask):
            # Obtener PnL de los trades reales
            real_train_indices = np.where(real_train_mask)[0]
            for i, idx in enumerate(real_train_indices):
                if i < len(df_real):
                    pnl = abs(df_real.iloc[i]['pnl'])
                    sample_weights[idx] = max(0.1, pnl)  # Mínimo peso 0.1
            
            # Normalizar pesos a [0.1, 1.0] para mayor estabilidad
            min_weight = sample_weights.min()
            max_weight = sample_weights.max()
            if max_weight > min_weight:  # Evitar división por cero
                sample_weights = 0.1 + 0.9 * (sample_weights - min_weight) / (max_weight - min_weight)
            
            print(f"  ✅ Pesos de impacto calculados: {len(sample_weights)} muestras")
            print(f"  📈 Rango de pesos: {sample_weights.min():.2f} - {sample_weights.max():.2f}")
    
    # Entrenar modelo con pesos de clases Y ponderación por impacto
    print("🧠 Entrenando Random Forest con clases balanceadas y ponderación de impacto...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight=class_weight_dict,  # Balanceo de clases
        n_jobs=-1
    )
    # ✅ CORRECCIÓN: Sintaxis correcta sample_weight=sample_weights
    model.fit(X_train, y_train, sample_weight=sample_weights)
    
    # Evaluar
    y_pred = model.predict(X_test)
    print("\n✅ Resultados del modelo (CON BALANCEO Y PONDERACIÓN):")
    print(classification_report(y_test, y_pred, target_names=['Short', 'Esperar', 'Long']))
    
    # Guardar modelo y features
    joblib.dump(model, 'ml_model.pkl')
    joblib.dump(feature_cols, 'feature_cols.pkl')
    print("\n💾 Modelo guardado como 'ml_model.pkl'")

if __name__ == "__main__":
    # ✅ Ajustar símbolo según modo de trading
    symbol_to_use = "BTC/USDT" if TRADING_MODE == "spot" else "BTC/USDT:USDT"
    train_ml_model(symbol=symbol_to_use, days=30)