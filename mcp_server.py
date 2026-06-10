"""Servidor MCP de Daily Tracker — expone tu tracking (SOLO LECTURA) a Claude.

Lee la MISMA `senal.db` que la app, así que Claude ve tus datos en vivo. Pensado
para correr en la VPS detrás de nginx (que pone la autenticación por token) y
escuchando solo en 127.0.0.1.

Arrancar:
  - Local (stdio, p. ej. para Claude Desktop en tu PC):   python mcp_server.py
  - Remoto (HTTP, para la VPS):              MCP_HTTP=1 python mcp_server.py

No expone ninguna herramienta de escritura: Claude puede consultar tu tracking,
nunca modificarlo.
"""
import os
from datetime import date, timedelta

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import db

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8765"))

# Detrás de nginx, la cabecera Host llega como tu dominio y la protección anti
# DNS-rebinding de MCP lo rechazaría con 421. nginx (con token) es ya la frontera
# de seguridad y solo 127.0.0.1 llega hasta aquí, así que la desactivamos. Si
# prefieres mantenerla, pon MCP_ALLOWED_HOST=tudominio.com en el servicio.
_allowed = os.environ.get("MCP_ALLOWED_HOST", "").strip()
if _allowed:
    _security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[_allowed, f"{HOST}:{PORT}", "127.0.0.1", "localhost"],
        allowed_origins=[f"https://{_allowed}", f"http://{_allowed}"])
else:
    _security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

mcp = FastMCP("Daily Tracker", host=HOST, port=PORT, transport_security=_security)

_PRIO = {3: "alta", 2: "media", 1: "baja"}


def _d(fecha):
    """Fecha pedida o, si viene vacía, hoy."""
    return fecha or date.today().isoformat()


def _tareas(fecha):
    d = _d(fecha)
    return {
        "fecha": d,
        "completadas_pct": db.tasks_pct(d),
        "tareas": [{"texto": t["text"], "hecha": bool(t["done"]),
                    "prioridad": _PRIO.get(t.get("priority") or 2)}
                   for t in db.get_tasks(d)],
    }


def _calorias(fecha):
    d = _d(fecha)
    tot = db.meals_totals(d)
    day = db.get_day(d) or {}
    burned = day.get("calories_burned")
    return {
        "fecha": d,
        "consumidas_kcal": round(tot["kcal"], 1),
        "macros_g": {"proteinas": round(tot["protein"], 1),
                     "carbohidratos": round(tot["carbs"], 1),
                     "grasas": round(tot["fat"], 1)},
        "quemadas_kcal": round(burned) if burned else None,
        "diferencia_kcal": round(burned - tot["kcal"]) if burned else None,
        "comidas": [{"nombre": m["name"], "tipo": m.get("meal_type"),
                     "kcal": m["kcal"], "proteinas": m["protein"],
                     "carbohidratos": m["carbs"], "grasas": m["fat"]}
                    for m in db.get_meals(d)],
    }


def _resumen(fecha):
    d = _d(fecha)
    day = db.get_day(d) or {}
    habitos = {db.LABELS.get(h, h): bool(day.get(h))
               for h in db.BOOL_HABITS if day.get(h) is not None}
    numericos = {db.LABELS.get(h, h): day.get(h)
                 for h in db.NUM_HABITS if day.get(h) is not None}
    whoop = {db.LABELS.get(w, w): day.get(w)
             for w in db.WHOOP_VARS if day.get(w) is not None}
    return {"fecha": d, "habitos": habitos, "numericos": numericos,
            "whoop": whoop, "tareas_pct": db.tasks_pct(d),
            "calorias": _calorias(d)}


@mcp.tool()
def tareas(fecha: str = "") -> dict:
    """Tareas de un día y % completado (ponderado por prioridad).

    fecha en formato AAAA-MM-DD; vacío = hoy."""
    return _tareas(fecha)


@mcp.tool()
def calorias(fecha: str = "") -> dict:
    """Calorías de un día: consumidas (con macros y desglose de comidas), quemadas
    (de Whoop) y su diferencia.

    fecha en formato AAAA-MM-DD; vacío = hoy."""
    return _calorias(fecha)


@mcp.tool()
def resumen_dia(fecha: str = "") -> dict:
    """Resumen completo de un día: hábitos, biometría de Whoop, tareas y calorías.

    fecha en formato AAAA-MM-DD; vacío = hoy."""
    return _resumen(fecha)


@mcp.tool()
def medias_calorias() -> dict:
    """Medias de calorías quemadas/consumidas/diferencia: últimos 30 días y global.

    Ignora el día de hoy (incompleto) y solo cuenta días con comidas y dato de Whoop."""
    today = date.today()
    rows = []
    for ds, v in db.meals_by_day().items():
        day = db.get_day(ds) or {}
        bd = day.get("calories_burned")
        do = date.fromisoformat(ds)
        if bd and do != today:
            rows.append((do, bd, v.get("kcal") or 0))

    def media(sel):
        if not sel:
            return None
        n = len(sel)
        ab = sum(b for _, b, _ in sel) / n
        ac = sum(c for _, _, c in sel) / n
        return {"dias": n, "quemadas_kcal": round(ab),
                "consumidas_kcal": round(ac), "diferencia_kcal": round(ab - ac)}

    recientes = [r for r in rows if r[0] >= today - timedelta(days=30)]
    return {"ultimos_30_dias": media(recientes), "global": media(rows)}


@mcp.tool()
def habitos_recientes(dias: int = 7) -> list:
    """Resumen (hábitos, biometría, tareas y calorías) de los últimos N días.

    dias entre 1 y 31 (por defecto 7); el primero es hoy."""
    dias = max(1, min(int(dias), 31))
    return [_resumen((date.today() - timedelta(days=i)).isoformat())
            for i in range(dias)]


if __name__ == "__main__":
    transport = "streamable-http" if os.environ.get("MCP_HTTP") else "stdio"
    mcp.run(transport=transport)
