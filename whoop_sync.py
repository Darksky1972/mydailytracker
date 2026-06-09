"""Sincronización de Whoop para el cron nocturno (sin Streamlit).

Uso:  /opt/senal/.venv/bin/python /opt/senal/whoop_sync.py [días]

Lee las credenciales de `.streamlit/secrets.toml` y usa el refresh token guardado
en la BD (hay que haber conectado una vez desde la web). Por defecto sincroniza
los últimos 7 días (fusión: no borra historial ni tus datos manuales).
"""
import sys
import tomllib
from pathlib import Path

import db
import whoop_api


def _secrets():
    path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)["whoop"]


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    db.init_db()
    if not whoop_api.is_connected():
        print("Whoop no conectado: conéctalo una vez desde la web.")
        return 1
    try:
        sec = _secrets()
    except (FileNotFoundError, KeyError):
        print("Falta .streamlit/secrets.toml con la sección [whoop].")
        return 1
    token = whoop_api.access_token(sec["client_id"], sec["client_secret"])
    res = whoop_api.sync(token, days=days)
    print(f"OK: {res['dias']} días, {res['workouts']} actividades "
          f"(ventana {days} días).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
