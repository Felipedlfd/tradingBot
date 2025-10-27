# data.py
import ccxt
import pandas as pd
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import BINANCE_API_KEY, BINANCE_API_SECRET, TRADING_MODE

def get_exchange():
    """
    Crea una instancia de Binance con reintentos HTTP integrados.
    """
    # Configurar reintentos HTTP inteligentes
    session = requests.Session()
    retries = Retry(
        total=5,  # máximo 5 intentos
        backoff_factor=1,  # espera: 1s, 2s, 4s, 8s...
        status_forcelist=[429, 500, 502, 503, 504],  # códigos a reintentar
        allowed_methods=["GET", "POST"]  # métodos seguros para reintentar
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    # Crear exchange con sesión personalizada
    if TRADING_MODE == "futures":
        exchange = ccxt.binanceusdm({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'adjustForTimeDifference': True,
                'defaultType': 'future'
            },
            'session': session
        })
    else:
        exchange = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'adjustForTimeDifference': True
            },
            'session': session
        })
    
    return exchange

def fetch_ohlcv(symbol, timeframe, limit=500):
    """
    Descarga datos OHLCV con reintentos automáticos para errores de red.
    """
    max_retries = 5
    for attempt in range(max_retries):
        try:
            exchange = get_exchange()
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # Validar datos
            if not ohlcv or len(ohlcv) == 0:
                raise ValueError("Datos vacíos recibidos de Binance")
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df.astype(float)
            
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            wait_time = 2 ** attempt  # espera exponencial
            logging.warning(f"🌐 Error de red (intento {attempt+1}/{max_retries}): {str(e)[:100]}... Reintentando en {wait_time}s")
            time.sleep(wait_time)
            
        except ccxt.NetworkError as e:
            wait_time = 2 ** attempt
            logging.warning(f"🌐 Error de red CCXT (intento {attempt+1}/{max_retries}): {str(e)[:100]}... Reintentando en {wait_time}s")
            time.sleep(wait_time)
            
        except ccxt.RateLimitExceeded as e:
            logging.warning(f"⏳ Límite de API excedido: {e}. Esperando 60s...")
            time.sleep(60)
            
        except ccxt.ExchangeError as e:
            if "Timestamp for this request was" in str(e):
                logging.error("⏰ Error de hora del sistema. Sincroniza la hora de Windows.")
                raise e
            else:
                logging.error(f"❌ Error de Binance: {e}")
                raise e
                
        except Exception as e:
            logging.error(f"💥 Error inesperado en fetch_ohlcv: {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(5)
    
    raise Exception(f"No se pudieron obtener datos de {symbol} después de {max_retries} intentos")