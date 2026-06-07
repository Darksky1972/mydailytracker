# ===========================================================================
#  Sube los cambios de CÓDIGO a la VPS y reinicia la app, todo de una vez.
#  Uso (desde PowerShell, en tu PC):
#     powershell -ExecutionPolicy Bypass -File "deploy\deploy_to_vps.ps1"
#  (No sube tus datos: senal.db y data/ se quedan como están en la VPS.)
# ===========================================================================
param(
    [string]$VpsHost = "root@72.61.167.56",
    [string]$Dest    = "/opt/senal"
)
$ErrorActionPreference = "Stop"

# Carpeta del proyecto = la carpeta padre de este script (deploy/).
$base  = Split-Path -Parent $PSScriptRoot
$files = "app.py", "db.py", "analysis.py", "seed.py", "whoop_import.py", "requirements.txt"
$src   = $files | ForEach-Object { Join-Path $base $_ }

Write-Host "==> Copiando código a $VpsHost ..." -ForegroundColor Cyan
scp $src "${VpsHost}:${Dest}/"

Write-Host "==> Reiniciando la app en la VPS ..." -ForegroundColor Cyan
ssh $VpsHost "chown senal:senal $Dest/*.py 2>/dev/null; systemctl restart senal; systemctl is-active senal"

Write-Host "==> Listo. Recarga https://dailytracker.cloud (Ctrl+F5)." -ForegroundColor Green
