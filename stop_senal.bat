@echo off
REM Detiene la instancia de Senal que escucha en el puerto 8501
REM (util para parar el arranque automatico en segundo plano).
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8501 "') do taskkill /f /pid %%a >nul 2>&1
echo Senal detenido (puerto 8501).
timeout /t 2 >nul
