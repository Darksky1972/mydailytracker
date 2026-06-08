#!/usr/bin/env bash
# Actualiza Señal en la VPS desde GitHub y reinicia la app.
# Uso (en la terminal de la VPS):  bash /opt/senal/deploy/update.sh
set -euo pipefail
cd /opt/senal
echo ">> Descargando últimos cambios de GitHub..."
git pull --ff-only origin main
chmod +x deploy/*.sh 2>/dev/null || true
echo ">> Reiniciando la app..."
systemctl restart senal
systemctl is-active senal
echo ">> Listo. Recarga https://dailytracker.cloud (Ctrl+F5)."
