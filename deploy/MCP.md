# Conectar tu Daily Tracker con Claude (MCP)

Esto levanta un **servidor MCP** en tu VPS que le da a Claude herramientas de
**solo lectura** para ver tu tracking (tareas, calorías, hábitos, biometría).
Lee la **misma `senal.db`** que la web, así que Claude ve tus datos **en vivo**.

Lo que Claude podrá responder, por ejemplo:
- «¿Qué tareas me quedan hoy?»
- «¿Cuántas kcal llevo y cuánto déficit?»
- «¿Cómo va mi recovery / mi sueño esta semana?»
- «¿Cuál es mi media de calorías consumidas del último mes?»

> Es **solo lectura**: Claude consulta, nunca cambia nada.

---

## Parte 1 — Montarlo en la VPS (una sola vez)

🖥️ **EN TU PC** primero sube el código:
```powershell
cd "c:\Users\User\OneDrive\Documentos\Páginas Web\Tracker"
git push origin main
```

☁️ **EN LA VPS** (conéctate con `ssh root@72.61.167.56`):

**1) Traer el código e instalar la dependencia nueva (`mcp`):**
```bash
bash /opt/senal/deploy/update.sh
```
(El `update.sh` ya hace `pip install -r requirements.txt`, que instala `mcp`.)

**2) Generar un token secreto** (apúntalo, lo usarás 2 veces):
```bash
openssl rand -hex 32
```

**3) Instalar y arrancar el servicio MCP:**
```bash
cp /opt/senal/deploy/senal-mcp.service /etc/systemd/system/senal-mcp.service
systemctl daemon-reload
systemctl enable --now senal-mcp
systemctl is-active senal-mcp        # debe decir: active
```

**4) Abrir el endpoint en nginx (protegido por el token):**
Edita el fichero de nginx de tu sitio:
```bash
nano /etc/nginx/sites-available/senal
```
Dentro del bloque `server { ... }` que tiene `listen 443` (el de HTTPS, donde
está `location / { ... }`), **pega** el contenido de
`/opt/senal/deploy/nginx-mcp.location` **justo después** del `location / { ... }`.
Cambia `PON_AQUI_TU_TOKEN_SECRETO` por el token del paso 2 (deja la palabra
`Bearer` delante: `Bearer abc123...`).

Comprueba y recarga:
```bash
nginx -t && systemctl reload nginx
```

**5) Probar que responde** (cambia TU_TOKEN):
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://dailytracker.cloud/mcp                       # -> 401 (sin token, correcto)
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer TU_TOKEN" https://dailytracker.cloud/mcp   # -> 400/406 (con token: pasa el login; ese código es normal con curl)
```
Si el primero da **401** y el segundo **NO** da 401, está bien.

---

## Parte 2 — Conectarlo a Claude

### Opción 1 — Claude Code (lo más rápido, en tu PC)
En una terminal de tu PC:
```powershell
claude mcp add --transport http daily-tracker https://dailytracker.cloud/mcp --header "Authorization: Bearer TU_TOKEN"
```
Luego, en Claude Code: `/mcp` para ver que está conectado, y ya puedes preguntar
«¿qué tareas tengo hoy?».

### Opción 2 — Claude Desktop (app de escritorio)
Necesita **Node.js** instalado (para el puente `mcp-remote`). Edita el archivo de
configuración de Claude Desktop:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

y añade:
```json
{
  "mcpServers": {
    "daily-tracker": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://dailytracker.cloud/mcp",
               "--header", "Authorization: Bearer TU_TOKEN"]
    }
  }
}
```
Reinicia Claude Desktop. Te aparecerá «daily-tracker» con sus herramientas.

### Opción 3 — Claude web/móvil (conector personalizado) — avanzado
La app web y de móvil sí pueden conectarse a un MCP remoto como **conector
personalizado**, pero exigen **OAuth** (no vale solo el token). Es un paso extra
más grande: hay que añadir una capa de OAuth al servidor. Cuando quieras lo
montamos; lo de arriba (PC) ya te da a Claude leyendo tus datos en vivo.

---

## Uso diario / mantenimiento (☁️ EN LA VPS)
```bash
systemctl status senal-mcp           # ¿está vivo?
journalctl -u senal-mcp -e           # ver errores
systemctl restart senal-mcp          # reiniciar
```
Cuando hagas cambios y ejecutes `bash /opt/senal/deploy/update.sh`, el servidor
MCP se reinicia solo (si ya está instalado).

## Seguridad
- El servidor escucha solo en `127.0.0.1`; al exterior se llega **solo** por
  `https://dailytracker.cloud/mcp` y **con el token**. Guarda el token como una
  contraseña; si se filtra, genera otro (paso 2) y cámbialo en nginx y en Claude.
- Son datos de salud personales: no compartas el token ni la URL con el token.
