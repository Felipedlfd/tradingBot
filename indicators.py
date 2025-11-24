import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

def add_indicators(df):
    df = df.copy()
    df['ema50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
    df['ema200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
    df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
    df['atr'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close']).average_true_range()
    df['body'] = abs(df['close'] - df['open'])
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    df['spread'] = (df['high'] - df['low']) / df['close']  # proxy de spread
    df['liquidez'] = df['volume'] / (df['spread'] + 1e-8)  # más alto = más líquido
    return df

def add_fibonacci_levels(df, window=50):
    """
    Añade niveles de Fibonacci (0.0, 0.236, 0.382, 0.618, 0.786, 1.0)
    basado en el rango más reciente (máximo y mínimo en 'window' velas).
    """
    df = df.copy()
    # Encontrar swing alto y bajo en la ventana
    recent_high = df['high'].rolling(window=window).max()
    recent_low = df['low'].rolling(window=window).min()
    
    # Rango Fibonacci
    df['fib_range'] = recent_high - recent_low
    
    # Niveles
    df['fib_0'] = recent_high  # 0.0
    df['fib_236'] = recent_high - 0.236 * df['fib_range']
    df['fib_382'] = recent_high - 0.382 * df['fib_range']
    df['fib_618'] = recent_high - 0.618 * df['fib_range']
    df['fib_786'] = recent_high - 0.786 * df['fib_range']
    df['fib_100'] = recent_low  # 1.0
    
    # ✅ NUEVO: Indicadores para mercados bajistas
    df['down_volume_ratio'] = (df['volume'] * (df['close'] < df['open']).astype(int)) / df['volume'].rolling(20).mean()
    df['down_trend_strength'] = (df['close'] < df['ema50']).astype(int) * (df['ema50'] < df['ema200']).astype(int)
    
    # ✅ NUEVO: Volatilidad en bajadas
    df['down_volatility'] = df['atr'] * (df['close'] < df['open']).astype(int)

    return df