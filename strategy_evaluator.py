# strategy_evaluator.py
import pandas as pd
from strategy_factory import STRATEGIES
from risk_manager import calculate_position_size

def evaluate_strategy(df, strategy_func, strategy_params, initial_capital=1000.0):
    capital = initial_capital
    position = None
    trades = []
    
    for i in range(200, len(df)):
        current_df = df.iloc[:i+1].copy()
        signal = strategy_func(current_df, strategy_params)
        current_price = current_df['close'].iloc[-1]
        
        # Cerrar posición si hay señal opuesta o SL/TP (simplificado)
        if position:
            # Lógica de cierre básica: invertir señal o después de N velas
            if signal == ('short' if position['type'] == 'long' else 'long'):
                pnl = (current_price - position['entry']) * position['size']
                if position['type'] == 'short':
                    pnl = -pnl
                capital += pnl
                trades.append({'pnl': pnl, 'exit_price': current_price})
                position = None
        
        # Abrir posición
        if position is None and signal in ['long', 'short']:
            sl = current_price * (0.99 if signal == 'long' else 1.01)  # SL fijo 1%
            size = calculate_position_size(capital, current_price, sl, 0.01)
            if size > 0:
                position = {'type': signal, 'size': size, 'entry': current_price}
                trades.append({'type': signal, 'price': current_price, 'size': size})
    
    # Métricas
    if not trades:
        return {'sharpe': -1, 'total_pnl': 0, 'win_rate': 0, 'trades': 0}
    
    closed_trades = [t for t in trades if 'pnl' in t]
    if not closed_trades:
        return {'sharpe': -1, 'total_pnl': 0, 'win_rate': 0, 'trades': 0}
    
    df_trades = pd.DataFrame(closed_trades)
    total_pnl = df_trades['pnl'].sum()
    win_rate = (df_trades['pnl'] > 0).mean()
    trades_count = len(df_trades)
    sharpe = total_pnl / (df_trades['pnl'].std() + 1e-6) if trades_count > 1 else total_pnl
    
    return {
        'sharpe': float(sharpe),
        'total_pnl': float(total_pnl),
        'win_rate': float(win_rate),
        'trades': int(trades_count)
    }