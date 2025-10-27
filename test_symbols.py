# test_symbols.py
import ccxt
exchange = ccxt.binanceusdm()
markets = exchange.load_markets()
print("Ejemplos de símbolos de futuros:")
for symbol in list(markets.keys())[:10]:
    if 'BTC' in symbol:
        print(symbol)