# strategy_selector.py
import pickle
from data import fetch_ohlcv
from indicators import add_indicators
from strategy_evaluator import evaluate_strategy
from strategy_factory import STRATEGIES

def select_best_strategy(symbol="BTC/USDT:USDT", days=7):
    print("🔍 Evaluando estrategias...")
    
    # Cargar datos
    df = fetch_ohlcv(symbol, "1h", limit=24*days)  # usar 1h para velocidad
    df = add_indicators(df)
    
    results = {}
    for name, func in STRATEGIES.items():
        params = {}  # podrías cargar parámetros optimizados por estrategia
        score = evaluate_strategy(df, func, params)
        results[name] = score
        print(f"  {name}: Sharpe={score['sharpe']:.2f}, PnL=${score['total_pnl']:.2f}")
    
    # Elegir la mejor por Sharpe
    best_name = max(results, key=lambda k: results[k]['sharpe'])
    
    # Guardar
    with open('best_strategy.pkl', 'wb') as f:
        pickle.dump({'name': best_name, 'metrics': results[best_name]}, f)
    
    print(f"\n✅ Estrategia seleccionada: {best_name}")
    return best_name, results[best_name]

def load_best_strategy():
    try:
        with open('best_strategy.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {'name': 'ema_rsi_wick', 'metrics': {}}