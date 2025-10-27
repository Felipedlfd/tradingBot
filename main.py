import logging
import schedule
import time
from agent import CryptoAgent
from config import TIMEFRAME

def main():
    agent = CryptoAgent()
    logging.info(f"🚀 Agente iniciado | Símbolo: {agent.symbol} | Modo: {agent.trading_mode}")
    
    # Ejecutar inmediatamente la primera vez
    agent.run_once()
    
    # Programar cada hora OJO VER SI MAS SEGUIDO
    
    if TIMEFRAME == "1m":
        schedule.every().minute.do(agent.run_once)
    elif TIMEFRAME == "5m":
        schedule.every(5).minutes.do(agent.run_once)  # ← clave para 5m
    elif TIMEFRAME == "15m":
        schedule.every(15).minutes.do(agent.run_once)
    elif TIMEFRAME == "1h":
          schedule.every().hour.at(":00").do(agent.run_once)
    else:
        schedule.every().hour.do(agent.run_once)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()