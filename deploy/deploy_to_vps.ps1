# ===========================================================================
#  Despliegue por Git: sube los cambios a GitHub y los aplica en la VPS.
#  Uso (desde PowerShell, en tu PC):
#     powershell -ExecutionPolicy Bypass -File "deploy\deploy_to_vps.ps1" -Message "que cambie"
#  Si omites -Message, se usa la fecha/hora como mensaje del commit.
#  (Tus datos no se tocan: senal.db y data/ están excluidos del repo.)
# ===========================================================================
param(
    [string]$Message = "",
    [string]$VpsHost = "root@72.61.167.56"
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not $Message) { $Message = "deploy " + (Get-Date -Format "yyyy-MM-dd HH:mm") }

Write-Host "==> Guardando cambios en Git..." -ForegroundColor Cyan
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -m $Message } else { Write-Host "   (no hay cambios nuevos que commitear)" }

Write-Host "==> Subiendo a GitHub..." -ForegroundColor Cyan
git push

Write-Host "==> Aplicando en la VPS (git pull + reinicio)..." -ForegroundColor Cyan
ssh $VpsHost "cd /opt/senal && git pull --ff-only && chmod +x deploy/*.sh 2>/dev/null; systemctl restart senal && systemctl is-active senal"

Write-Host "==> Listo. Recarga https://dailytracker.cloud (Ctrl+F5)." -ForegroundColor Green
