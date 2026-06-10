#!/usr/bin/env bash
# Actualiza Señal en la VPS desde GitHub y reinicia la app.
# Uso (en la terminal de la VPS):  bash /opt/senal/deploy/update.sh
set -euo pipefail
cd /opt/senal
# Ignora cambios de permisos para que el chmod +x de abajo no haga fallar el pull.
git config core.fileMode false
echo ">> Descargando últimos cambios de GitHub..."
git pull --ff-only origin main
chmod +x deploy/*.sh 2>/dev/null || true
echo ">> Instalando dependencias (si hay nuevas)..."
/opt/senal/.venv/bin/pip install -q -r requirements.txt || true
echo ">> Reiniciando la app..."
systemctl restart senal
systemctl is-active senal
# Reinicia el servidor MCP solo si ya está instalado (ver deploy/MCP.md).
if systemctl list-unit-files | grep -q '^senal-mcp.service'; then
    echo ">> Reiniciando el servidor MCP..."
    systemctl restart senal-mcp
    systemctl is-active senal-mcp
fi
echo ">> Listo. Recarga https://dailytracker.cloud (Ctrl+F5)."
