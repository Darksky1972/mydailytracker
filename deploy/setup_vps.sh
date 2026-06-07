#!/usr/bin/env bash
# ===========================================================================
#  Despliegue de Senal en una VPS Ubuntu/Debian (Hostinger).
#  Ejecutar como root (o con sudo) DESPUES de copiar los archivos a /opt/senal.
#
#    sudo bash deploy/setup_vps.sh  senal.tudominio.com  tu_usuario_login
#
#  Deja la app corriendo (systemd) detras de Nginx con login (Basic Auth).
#  Al final te recuerda el comando de Certbot para activar HTTPS.
# ===========================================================================
set -euo pipefail

APP_DIR="/opt/senal"
SERVICE_USER="senal"
DOMAIN="${1:?Uso: sudo bash setup_vps.sh DOMINIO USUARIO_LOGIN}"
AUTH_USER="${2:?Uso: sudo bash setup_vps.sh DOMINIO USUARIO_LOGIN}"

echo ">> [1/6] Instalando paquetes del sistema..."
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx apache2-utils \
                   certbot python3-certbot-nginx

echo ">> [2/6] Creando usuario de servicio '$SERVICE_USER'..."
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

echo ">> [3/6] Creando entorno virtual e instalando dependencias..."
sudo -u "$SERVICE_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo ">> [4/6] Instalando y arrancando el servicio systemd..."
cp "$APP_DIR/deploy/senal.service" /etc/systemd/system/senal.service
systemctl daemon-reload
systemctl enable --now senal
sleep 2
systemctl --no-pager --full status senal | head -n 12 || true

echo ">> [5/6] Configurando Nginx..."
sed "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" "$APP_DIR/deploy/nginx-senal.conf" \
    > /etc/nginx/sites-available/senal
ln -sf /etc/nginx/sites-available/senal /etc/nginx/sites-enabled/senal
if [ -e /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl reload nginx

echo ">> [6/6] Crea el usuario/contrasena de acceso (login del navegador)..."
htpasswd -c /etc/nginx/.htpasswd-senal "$AUTH_USER"
chown root:www-data /etc/nginx/.htpasswd-senal
chmod 640 /etc/nginx/.htpasswd-senal

# Abre el firewall si ufw esta activo.
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
    ufw allow 'Nginx Full' || true
fi

echo
echo "==========================================================================="
echo " LISTO. La app ya corre en 127.0.0.1:8501 detras de Nginx (con login)."
echo
echo " Ultimo paso: con el DNS de $DOMAIN apuntando a esta VPS, activa HTTPS:"
echo
echo "     sudo certbot --nginx -d $DOMAIN"
echo
echo " Despues entra en:  https://$DOMAIN     (usuario: $AUTH_USER)"
echo "==========================================================================="
