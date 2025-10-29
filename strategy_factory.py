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

# strategy_factory.py
def strategy_fibonacci_786(df, params):
    """
    Estrategia: Compra en retroceso al 78.6% de Fibonacci con confirmación de vela.
    Inspirada en @Eliz883.
    """
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Verificar que haya niveles Fibonacci
    if pd.isna(last['fib_786']):
        return None
    
    # Zona de entrada: precio cerca de fib_786
    margin = 0.002  # 0.2% de margen
    near_786 = abs(last['close'] - last['fib_786']) / last['fib_786'] < margin
    
    # Confirmación de vela alcista
    bullish_candle = last['close'] > last['open']
    
    # Tendencia previa alcista (precio cerca del swing alto)
    in_uptrend = (last['high'] - last['fib_0']) / last['fib_0'] < 0.01
    
    if near_786 and bullish_candle and in_uptrend:
        return 'long'
    
    return None

# Registro de estrategias
STRATEGIES = {
    'ema_rsi_wick': strategy_ema_rsi_wick,
    'macd_histogram': strategy_macd_histogram,
    'bollinger_breakout': strategy_bollinger_breakout,
    'fibonacci_786': strategy_fibonacci_786,
}