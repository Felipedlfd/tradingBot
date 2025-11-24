# ml_trainer.py
import pandas as pd
import numpy as np
import logging
import joblib
import time
import json
from datetime import datetime
from pathlib import Path
from config import SYMBOL, TRADING_MODE
from data import fetch_ohlcv
from indicators import add_indicators
from utils_ml import load_real_trades_as_labels
from risk_manager import calculate_position_size
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.utils.class_weight import compute_class_weight

def create_features_and_labels(df, lookahead=10, threshold=0.015):
    """
    Crea features (X) y etiquetas (y) para entrenamiento.
    """
    df = df.copy()
    
    # ✅ AÑADIR INDICADORES PRIMERO
    df = add_indicators(df)
    
    # Calcular retorno futuro
    df['future_close'] = df['close'].shift(-lookahead)
    df['future_return'] = (df['future_close'] - df['close']) / df['close']
    
    # Etiquetas
    df['label'] = 0
    df.loc[df['future_return'] > threshold, 'label'] = 1    # Long
    df.loc[df['future_return'] < -threshold, 'label'] = -1  # Short
    
    # Eliminar NaN
    df = df.dropna()
    
    # Features
    feature_cols = [
        'open', 'high', 'low', 'close', 'volume',
        'ema50', 'ema200', 'rsi', 'atr',
        'upper_wick', 'lower_wick', 'body',
        'liquidez'
    ]
    
    # ✅ VERIFICAR QUE TODAS LAS COLUMNAS EXISTAN
    missing_cols = [col for col in feature_cols if col not in df.columns]
    if missing_cols:
        logging.warning(f"⚠️ Columnas faltantes en el DataFrame: {missing_cols}")
        # Filtrar solo columnas existentes
        feature_cols = [col for col in feature_cols if col in df.columns]
    
    X = df[feature_cols]
    y = df['label']
    
    return X, y, feature_cols

def train_ml_model(symbol="BTC/USDT:USDT", days=30):
    print("📥 Descargando datos históricos...")
    df = fetch_ohlcv(symbol, "1h", limit=24*days)
    
    if df.empty:
        print("❌ Error al cargar datos.")
        return
    
    # ✅ VERIFICAR ESTRUCTURA DEL DATAFRAME
    print(f"🔍 Estructura inicial del DataFrame:")
    print(f"  - Columnas disponibles: {list(df.columns)}")
    print(f"  - Tamaño: {df.shape}")
    
    # ✅ FORZAR AÑADIR INDICADORES DESDE EL PRINCIPIO
    df = add_indicators(df)
    print(f"📊 Columnas después de añadir indicadores: {list(df.columns)}")
    
    print("⚙️  Creando features y etiquetas...")
    X, y, feature_cols = create_features_and_labels(df, lookahead=10, threshold=0.015)
    
    # ✅ PASO CLAVE: Cargar trades reales como datos adicionales
    df_real = load_real_trades_as_labels(symbol=symbol, min_pnl_abs=1.0)
    
    X_real = pd.DataFrame()
    y_real = pd.Series(dtype='int')
    
    if not df_real.empty:
        print(f"➕ Añadiendo {len(df_real)} trades reales al entrenamiento...")
        
        # ✅ CREAR MAPPING PARA BÚSQUEDAS RÁPIDAS
        timestamp_to_index = {ts: idx for idx, ts in enumerate(df.index)}
        
        X_real_list = []
        y_real_list = []
        
        for _, trade in df_real.iterrows():
            try:
                trade_ts = trade['timestamp']
                if trade_ts in timestamp_to_index:
                    idx = timestamp_to_index[trade_ts]
                else:
                    # Buscar índice más cercano
                    closest_idx = df.index.get_indexer([trade_ts], method='nearest')
                    idx = closest_idx[0]
                
                if 0 <= idx < len(df):
                    features = df.iloc[idx][feature_cols]
                    X_real_list.append(features)
                    y_real_list.append(trade['label'])
                else:
                    logging.warning(f"⚠️ Índice inválido {idx} para timestamp {trade_ts}")
            except Exception as e:
                logging.warning(f"⚠️ Error procesando trade {trade.get('timestamp', 'N/A')}: {str(e)}")
        
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
    
    # 💡 ✅ BALANCEO DE CLASES
    classes = np.array(sorted(set(y_train)))  # ✅ CONVERTIR A NUMPY ARRAY
    class_weights = compute_class_weight('balanced', classes=classes, y=y_train)
    class_weight_dict = dict(zip(classes.tolist(), class_weights.tolist()))  # ✅ Convertir de vuelta a lista para el dict
    print(f"⚖️ Pesos de clases calculados: {class_weight_dict}")
    
    # 💡 ✅ PONDERACIÓN POR IMPACTO
    sample_weights = np.ones(len(X_train))
    
    if not X_real.empty:
        print("📊 Preparando ponderación por impacto de trades...")
        
        # Identificar índices de trades reales en entrenamiento
        real_indices = np.array([i for i in range(len(X_train)) if i >= len(X_train) - len(X_real)])
        
        if len(real_indices) > 0:
            for i, idx in enumerate(real_indices):
                if i < len(df_real) and idx < len(sample_weights):
                    pnl = abs(df_real.iloc[i]['pnl'])
                    sample_weights[idx] = max(0.1, pnl)
            
            # Normalizar pesos
            min_weight = sample_weights.min()
            max_weight = sample_weights.max()
            if max_weight > min_weight:
                sample_weights = 0.1 + 0.9 * (sample_weights - min_weight) / (max_weight - min_weight)
            
            print(f"  ✅ Pesos de impacto calculados: {len(sample_weights)} muestras")
            print(f"  📈 Rango de pesos: {sample_weights.min():.2f} - {sample_weights.max():.2f}")
    
    # Entrenar modelo
    print("🧠 Entrenando Random Forest con clases balanceadas y ponderación de impacto...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight=class_weight_dict,
        n_jobs=-1
    )
    model.fit(X_train, y_train, sample_weight=sample_weights)
    
    # Evaluar
    y_pred = model.predict(X_test)
    print("\n✅ Resultados del modelo (CON BALANCEO Y PONDERACIÓN):")
    print(classification_report(y_test, y_pred, target_names=['Short', 'Esperar', 'Long']))
    
    # Guardar modelo
    joblib.dump(model, 'ml_model.pkl')
    joblib.dump(feature_cols, 'feature_cols.pkl')
    print("\n💾 Modelo guardado como 'ml_model.pkl'")

if __name__ == "__main__":
    symbol_to_use = "BTC/USDT" if TRADING_MODE == "spot" else "BTC/USDT:USDT"
    train_ml_model(symbol=symbol_to_use, days=1000)