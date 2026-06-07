# Guía paso a paso para publicar Señal en tu VPS (Ubuntu 24.04)

Pensada para alguien **sin experiencia con VPS**. Resultado final:
`https://senal.tudominio.com`, con **contraseña** y **candado de seguridad (HTTPS)**.

Tu IP de VPS: **72.61.167.56**

---

## ⭐ RUTA FÁCIL: usar el VS Code de Hostinger (recomendado)
Hostinger te deja abrir un **VS Code dentro de la VPS, en el navegador** (botón
**"Manage App"**). Eso te da una **Terminal** y un **explorador de archivos** del
servidor, así que **te ahorras el SSH y el `scp` de PowerShell**.

Si usas esta ruta, los pasos quedan así:
1. **DNS** (igual que abajo, en el panel de Hostinger): registro `A`, nombre
   `senal`, apunta a `72.61.167.56`.
2. Abre **Manage App** (si pide contraseña, créala con el botón **Reset** que hay
   junto a *Password*). Dentro: **Terminal → New Terminal**.
3. En esa terminal: `mkdir -p /opt/senal` y luego **File → Open Folder →
   `/opt/senal`**.
4. **Arrastra** desde el Explorador de Windows a la lista de archivos de VS Code:
   `app.py`, `db.py`, `analysis.py`, `seed.py`, `whoop_import.py`,
   `requirements.txt`, `senal.db`, y las carpetas `data` y `deploy`.
   (NO subas `.venv`.)
5. En la terminal de VS Code:
   `cd /opt/senal && bash deploy/setup_vps.sh senal.tudominio.com mi_usuario`
6. `certbot --nginx -d senal.tudominio.com`
7. Entra en `https://senal.tudominio.com`.

> Si un comando dice "permission denied", ponle **`sudo`** delante. No hace falta
> dejar el VS Code abierto para que la app funcione: la mantiene `systemd`.

El resto del documento explica la **ruta clásica** (SSH + `scp` desde PowerShell),
por si la prefieres. Los pasos del servidor (instalar, HTTPS, uso diario) son los
mismos en ambas rutas.

---

## Conceptos en 30 segundos
- **VPS**: un ordenador de Hostinger encendido siempre en internet. Le hablas
  escribiendo comandos por una conexión llamada **SSH**.
- **Dominio (DNS)**: hacer que `senal.tudominio.com` apunte a la IP de la VPS.
- **Nginx**: el "portero" que pide la contraseña y da el HTTPS.
- **systemd**: lo que mantiene la app encendida siempre (aunque reinicies la VPS).

### ⚠️ MUY IMPORTANTE: dos sitios distintos donde escribir comandos
Vas a usar **dos tipos de ventana**. No los mezcles:

- 🖥️ **EN TU PC** = una ventana de **PowerShell** en tu Windows.
- ☁️ **EN LA VPS** = esa MISMA ventana, pero **después de conectarte por SSH**
  (verás que el texto del principio de la línea cambia a algo como `root@...:~#`).

Cada bloque de abajo dice si es 🖥️ EN TU PC o ☁️ EN LA VPS.

---

## Lo que necesitas tener a mano (del panel de Hostinger)
Entra en **hpanel.hostinger.com** → tu VPS. Apunta:
1. **La IP** de la VPS (algo como `82.123.45.67`).
2. **Usuario SSH**: normalmente `root`.
3. **Contraseña de root**: si no la sabes, en el panel de la VPS hay un botón
   para **cambiar/restablecer la contraseña de root**. Ponle una y guárdala.

En esta guía, donde veas `IP_DE_TU_VPS` y `senal.tudominio.com`, pon los tuyos.

---

## PASO 1 — Apuntar el dominio a la VPS (hazlo primero, tarda en "propagar")
Si tu dominio está en Hostinger: hPanel → **Dominios** → tu dominio → **Zona DNS**.
Crea un registro nuevo:

| Campo  | Valor          |
|--------|----------------|
| Tipo   | `A`            |
| Nombre | `senal`        |
| Apunta a / Contenido | `IP_DE_TU_VPS` |
| TTL    | deja el que venga |

Guarda. Esto crea `senal.tudominio.com`. Puede tardar de 5 minutos a 2 horas.

**Comprobar que ya apunta** (🖥️ EN TU PC):
```powershell
ping senal.tudominio.com
```
Si responde con la IP de tu VPS, ✅ listo. Si da error o IP distinta, espera y
repite. (Puedes seguir con el PASO 2 mientras tanto.)

---

## PASO 2 — Copiar los archivos de tu PC a la VPS
🖥️ **EN TU PC** (abre PowerShell). Copia y pega tal cual, cambiando `IP_DE_TU_VPS`:

```powershell
$base = "c:\Users\User\OneDrive\Documentos\Páginas Web\Tracker"
ssh root@IP_DE_TU_VPS "mkdir -p /opt/senal"
```
- La **primera vez** te dirá algo como *"Are you sure you want to continue
  connecting (yes/no)?"* → escribe **`yes`** y Enter.
- Luego te pide la **contraseña de root**. **Al escribirla NO se ve nada** (ni
  puntitos). Es normal: escríbela a ciegas y pulsa Enter.

Ahora copia el código y tus datos (dos comandos; la contraseña te la pedirá otra vez):
```powershell
scp "$base\app.py" "$base\db.py" "$base\analysis.py" "$base\seed.py" "$base\whoop_import.py" "$base\requirements.txt" "$base\senal.db" root@IP_DE_TU_VPS:/opt/senal/
```
```powershell
scp -r "$base\data" "$base\deploy" root@IP_DE_TU_VPS:/opt/senal/
```
> Se copia `senal.db` porque guarda tus datos manuales (Japonés, Pantalla noche,
> tareas) que no están en los CSV. NO se copia el `.venv` (es de Windows; la VPS
> crea el suyo).

---

## PASO 3 — Conectarte a la VPS
🖥️ **EN TU PC**:
```powershell
ssh root@IP_DE_TU_VPS
```
Mete la contraseña (a ciegas). Cuando el inicio de la línea cambie a algo como
`root@srv123:~#`, **ya estás dentro de la VPS** ☁️. A partir de aquí los comandos
se ejecutan en la VPS.

---

## PASO 4 — Instalar y arrancar todo (un solo comando)
☁️ **EN LA VPS**. Cambia `senal.tudominio.com` y elige el usuario de login que
quieras (p. ej. tu nombre):
```bash
cd /opt/senal
bash deploy/setup_vps.sh senal.tudominio.com mi_usuario
```
Tardará 1-3 minutos (instala cosas). Al final te pedirá:
```
New password:
Re-type new password:
```
Esa es **la contraseña con la que entrarás a la web** (otra vez a ciegas, no se
ve). Apúntala.

Cuando termine, verás un recuadro que dice *"LISTO"* y te recuerda el comando del
PASO 5.

> Si saliera el error `‘\r’: command not found`, ejecuta esto y repite el comando:
> ```bash
> apt install -y dos2unix && dos2unix deploy/*.sh
> ```

---

## PASO 5 — Activar el candado de seguridad (HTTPS)
☁️ **EN LA VPS** (solo cuando el `ping` del PASO 1 ya daba tu IP):
```bash
certbot --nginx -d senal.tudominio.com
```
Te hará unas preguntas:
1. **Email**: pon el tuyo (para avisos del certificado). Enter.
2. **Términos (A)gree**: escribe `Y` y Enter.
3. **Boletín de noticias**: `N` y Enter.
4. Si pregunta por **redirigir HTTP a HTTPS**, elige la opción **2** (redirect).

Si dice *"Congratulations"*, ✅ ya tienes HTTPS.

---

## PASO 6 — ¡Entrar!
En cualquier navegador (móvil o PC): `https://senal.tudominio.com`
Te pedirá el **usuario y la contraseña** del PASO 4. Dentro está tu app. 🎉

---

## PASO 7 (opcional pero recomendado) — Backup automático de tus datos
☁️ **EN LA VPS**, copia y pega este bloque entero:
```bash
chmod +x /opt/senal/deploy/backup_senal.sh
echo "0 3 * * * root /opt/senal/deploy/backup_senal.sh" > /etc/cron.d/senal-backup
echo "Backup diario configurado a las 3:00. Copias en /opt/senal/backups/"
```
Guarda una copia de `senal.db` cada noche (conserva las últimas 14).

**Descargar una copia a tu PC** (🖥️ EN TU PC):
```powershell
scp -r root@IP_DE_TU_VPS:/opt/senal/backups "$base\backups_vps"
```

---

## Uso del día a día (todo ☁️ EN LA VPS, tras conectar con `ssh root@IP_DE_TU_VPS`)

**¿Está funcionando? / ver errores:**
```bash
systemctl status senal
journalctl -u senal -f     # registro en vivo; Ctrl+C para salir
```

**Reiniciar la app (tras cambiar código):**
```bash
systemctl restart senal
```

**Apagar / encender la app:**
```bash
systemctl stop senal
systemctl start senal
```

**Cambiar la contraseña de la web:**
```bash
htpasswd /etc/nginx/.htpasswd-senal mi_usuario
systemctl reload nginx
```

**Actualizar la app cuando cambies algo en tu PC:**
1. 🖥️ EN TU PC: vuelve a copiar el/los archivo(s) cambiados, p. ej.:
   ```powershell
   scp "$base\app.py" root@IP_DE_TU_VPS:/opt/senal/
   ```
2. ☁️ EN LA VPS:
   ```bash
   chown senal:senal /opt/senal/*.py
   systemctl restart senal
   ```

---

## ⚠️ Importante: ahora tendrás tus datos en DOS sitios
La `senal.db` de tu PC y la de la VPS son **independientes**. Si apuntas hábitos
en la web (VPS) y también en el PC, **se desincronizan**.

Recomendación: usa **solo la de la VPS** (entras desde cualquier sitio) y deja la
del PC para cuando programes cambios. El backup del PASO 7 te protege la de la VPS.

---

## Si algo no va (problemas típicos)
- **La web no carga**: en hPanel de Hostinger, revisa que el **cortafuegos**
  permita los puertos **80** y **443** (y el **22** para SSH).
- **`certbot` falla**: casi siempre es que el **DNS aún no apunta** (el `ping` del
  PASO 1 no daba tu IP) o el puerto 80 está cerrado. Espera y repite.
- **Pide contraseña una y otra vez por SSH**: la estás escribiendo mal (recuerda
  que no se ve). O restablece la contraseña de root en el panel de Hostinger.
- **Error 502 Bad Gateway**: la app no está arrancada → `systemctl status senal`
  y mira el error con `journalctl -u senal -e`.
- Pégame el texto del error y lo resolvemos.
