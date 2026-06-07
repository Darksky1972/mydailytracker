@echo off
REM ============================================================
REM  Lanzador de Senal (Streamlit).
REM  Doble clic: abre la app y, si no esta en marcha, la inicia.
REM  Cierra esta ventana para detener la aplicacion.
REM ============================================================
cd /d "%~dp0"

REM Si ya hay algo escuchando en el puerto 8501, solo abre el navegador.
netstat -an | findstr "LISTENING" | findstr ":8501 " >nul 2>&1
if %errorlevel%==0 (
  echo Senal ya esta en marcha. Abriendo navegador...
  start "" "http://localhost:8501"
  timeout /t 2 >nul
  exit /b
)

echo Iniciando Senal en http://localhost:8501
echo (Cierra esta ventana para detener la aplicacion.)
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501
