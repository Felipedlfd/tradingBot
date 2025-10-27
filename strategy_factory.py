# strategy_factory.py
import pandas as pd

def strategy_ema_rsi_wick(df, params):
    """Tu estrategia actual"""
    last = df.iloc[-1]
    if pd.isna(last['ema200']) or pd.isna(last['rsi']):
        return None
    # Long
    if (last['close'] > last['ema50'] > last['ema200'] and
        last['rsi'] < params.get('rsi_upper', 60) and
        last['lower_wick'] > params.get('wick_ratio', 2.0) * last['body']):
        return 'long'
    # Short
    if (last['close'] < last['ema50'] < last['ema200'] and
        last['rsi'] > params.get('rsi_lower', 40) and
        last['upper_wick'] > params.get('wick_ratio', 2.0) * last['body']):
        return 'short'
    return None

def strategy_macd_histogram(df, params):
    """Nueva estrategia: cruces de MACD"""
    from ta.trend import MACD
    macd = MACD(close=df['close'])
    df = df.copy()
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['histogram'] = df['macd'] - df['macd_signal']
    
    if len(df) < 2:
        return None
    prev, last = df.iloc[-2], df.iloc[-1]
    
    # Long: histograma pasa de negativo a positivo
    if prev['histogram'] < 0 and last['histogram'] > 0:
        return 'long'
    # Short: histograma pasa de positivo a negativo
    if prev['histogram'] > 0 and last['histogram'] < 0:
        return 'short'
    return None

def strategy_bollinger_breakout(df, params):
    """Estrategia: ruptura de bandas de Bollinger"""
    from ta.volatility import BollingerBands
    bb = BollingerBands(close=df['close'])
    df = df.copy()
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    last = df.iloc[-1]
    
    if last['close'] > last['bb_high']:
        return 'short'  # sobrecompra → short
    if last['close'] < last['bb_low']:
        return 'long'   # sobreventa → long
    return None

# Registro de estrategias
STRATEGIES = {
    'ema_rsi_wick': strategy_ema_rsi_wick,
    'macd_histogram': strategy_macd_histogram,
    'bollinger_breakout': strategy_bollinger_breakout,
}