@echo off
echo 🖥️  Iniciando Dashboard de Streamlit...
echo Espera unos segundos... la app se abrirá automáticamente.
call venv\Scripts\activate
cd dashboard
start /B "" streamlit run app.py --server.port=8501 --server.headless=true
timeout /t 5 /nobreak >nul
start "" "http://localhost:8501"