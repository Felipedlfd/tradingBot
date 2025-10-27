import logging
import os
import sys
from pathlib import Path

# Asegurar que el directorio actual esté en el path
sys.path.insert(0, str(Path(__file__).parent))

# Crear carpeta de logs
os.makedirs("logs", exist_ok=True)

# Configurar logging a archivo y consola
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/trading.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

from main import main

if __name__ == "__main__":
    logging.info("🟢 Iniciando Crypto Trading Agent (Windows Service Mode)")
    try:
        main()
    except KeyboardInterrupt:
        logging.info("🛑 Agente detenido por el usuario.")
    except Exception as e:
        logging.error(f"💥 Error crítico: {e}", exc_info=True)