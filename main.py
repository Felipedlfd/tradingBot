import logging
import schedule
import time
from agent import CryptoAgent
from config import SIGNAL_TIMEFRAME, EXECUTION_TIMEFRAME

def main():
    agent = CryptoAgent()
    logging.info(f"🚀 Agente iniciado | Señales: {SIGNAL_TIMEFRAME} | Ejecución: {EXECUTION_TIMEFRAME}")
    
    agent.run_once()
    
    # Programar ejecución en EXECUTION_TIMEFRAME
    if EXECUTION_TIMEFRAME == "1m":
        schedule.every().minute.do(agent.run_once)
    elif EXECUTION_TIMEFRAME == "5m":
        schedule.every(5).minutes.do(agent.run_once)
    elif EXECUTION_TIMEFRAME == "15m":
        schedule.every(15).minutes.do(agent.run_once)
    elif EXECUTION_TIMEFRAME == "1h":
          schedule.every().hour.at(":00").do(agent.run_once)
    else:
        schedule.every().hour.do(agent.run_once)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()