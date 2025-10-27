import pandas as pd

def detect_wick_fill_buy(df):
    if len(df) < 2: return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if (last['lower_wick'] > 2 * last['body']) and (last['close'] > last['open']):
        if prev['low'] > last['low']:
            return True
    return False

def detect_wick_fill_sell(df):
    if len(df) < 2: return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if (last['upper_wick'] > 2 * last['body']) and (last['close'] < last['open']):
        if prev['high'] < last['high']:
            return True
    return False

def should_enter_long(df):
    last = df.iloc[-1]
    if pd.isna(last['ema200']) or pd.isna(last['rsi']):
        return False
    if last['close'] > last['ema50'] > last['ema200']:
        if last['rsi'] < 60:
            if detect_wick_fill_buy(df):
                return True
    return False

def should_enter_short(df):
    last = df.iloc[-1]
    if pd.isna(last['ema200']) or pd.isna(last['rsi']):
        return False
    if last['close'] < last['ema50'] < last['ema200']:
        if last['rsi'] > 40:
            if detect_wick_fill_sell(df):
                return True
    return False

def should_exit_position(df, entry_price, position_type, atr_multiple=1.5):
    last = df.iloc[-1]
    atr = last['atr']
    if position_type == 'long':
        sl = entry_price - atr * atr_multiple
        tp = entry_price + atr * atr_multiple * 2
        sl_hit = last['close'] <= sl
        tp_hit = last['close'] >= tp
    else:  # short
        sl = entry_price + atr * atr_multiple
        tp = entry_price - atr * atr_multiple * 2
        sl_hit = last['close'] >= sl
        tp_hit = last['close'] <= tp
    return sl_hit, tp_hit, sl, tp