"""Cliente de la API de Whoop (v2) para Señal — Fase 1: OAuth + descarga.

Single-user: autorizas UNA vez (flujo en la propia web) para obtener un refresh
token, que se guarda en la tabla `meta` de la BD. Después se renueva el access
token bajo demanda. Whoop ROTA el refresh token, así que guardamos el nuevo cada
vez. Las credenciales (client_id/secret/redirect_uri) viven en
`.streamlit/secrets.toml` (fuera de git) y se pasan desde app.py.

El mapeo a los campos de Señal y el volcado a la BD se añadirán (Fase 2) cuando
verifiquemos la estructura real de las respuestas con "Probar conexión".
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

import db

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer/v2"
SCOPES = ["offline", "read:recovery", "read:cycles", "read:sleep",
          "read:workout", "read:profile"]
_RT_KEY = "whoop_refresh_token"   # clave del refresh token en la tabla meta


def is_connected():
    return bool(db.get_meta(_RT_KEY))


def disconnect():
    db.set_meta(_RT_KEY, "")


def authorize_url(client_id, redirect_uri, state):
    """URL a la que mandar al usuario para que autorice la app en Whoop."""
    return AUTH_URL + "?" + urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
    })


def exchange_code(code, client_id, client_secret, redirect_uri):
    """Cambia el código de autorización por tokens y guarda el refresh token."""
    r = requests.post(TOKEN_URL, timeout=30, data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    })
    r.raise_for_status()
    tok = r.json()
    if tok.get("refresh_token"):
        db.set_meta(_RT_KEY, tok["refresh_token"])
    return tok.get("access_token")


def access_token(client_id, client_secret):
    """Usa el refresh token guardado para obtener un access token nuevo.
    Guarda el refresh token rotado que devuelve Whoop."""
    rt = db.get_meta(_RT_KEY)
    if not rt:
        return None
    r = requests.post(TOKEN_URL, timeout=30, data={
        "grant_type": "refresh_token",
        "refresh_token": rt,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "offline",
    })
    r.raise_for_status()
    tok = r.json()
    if tok.get("refresh_token"):
        db.set_meta(_RT_KEY, tok["refresh_token"])
    return tok.get("access_token")


def _get_all(path, token, start=None, end=None, limit=25, max_pages=60):
    """Descarga todos los registros (paginado con next_token) de una colección."""
    out = []
    params = {"limit": limit}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    next_token = None
    for _ in range(max_pages):
        if next_token:
            params["nextToken"] = next_token
        r = requests.get(API_BASE + path, timeout=30,
                         headers={"Authorization": f"Bearer {token}"}, params=params)
        r.raise_for_status()
        j = r.json()
        out.extend(j.get("records", []))
        next_token = j.get("next_token")
        if not next_token:
            break
    return out


def fetch_recent(token, days=14):
    """Trae los datos recientes EN CRUDO de los 4 endpoints (para inspección)."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)
             ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "cycles": _get_all("/cycle", token, start=start),
        "recoveries": _get_all("/recovery", token, start=start),
        "sleeps": _get_all("/activity/sleep", token, start=start),
        "workouts": _get_all("/activity/workout", token, start=start),
    }
