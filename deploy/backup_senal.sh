#!/usr/bin/env bash
# Copia de seguridad diaria de senal.db. La instala el cron de /etc/cron.d/senal-backup.
set -euo pipefail
mkdir -p /opt/senal/backups
cp /opt/senal/senal.db "/opt/senal/backups/senal-$(date +%F).db"
# Conserva solo las 14 copias más recientes.
ls -1t /opt/senal/backups/senal-*.db 2>/dev/null | tail -n +15 | xargs -r rm --
