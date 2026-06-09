"""Cliente de la API de Whoop (v2) para Señal — Fase 1: OAuth + descarga.

Single-user: autorizas UNA vez (flujo en la propia web) para obtener un refresh
token, que se guarda en la tabla `meta` de la BD. Después se renueva el access
token bajo demanda. Whoop ROTA el refresh token, así que guardamos el nuevo cada
vez. Las credenciales (client_id/secret/redirect_uri) viven en
`.streamlit/secrets.toml` (fuera de git) y se pasan desde app.py.

El mapeo a los campos de Señal y el volcado a la BD se añadirán (Fase 2) cuando
verifiquemos la estructura real de las respuestas con "Probar conexión".
"""
from collections import defaultdict
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


def fetch_recent(token, days=30):
    """Trae los datos recientes EN CRUDO de los 4 endpoints."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)
             ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "cycles": _get_all("/cycle", token, start=start),
        "recoveries": _get_all("/recovery", token, start=start),
        "sleeps": _get_all("/activity/sleep", token, start=start),
        "workouts": _get_all("/activity/workout", token, start=start),
    }


# --- mapeo de la API al modelo de Señal (mismo dateado que el import de CSV) ---
def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f          # descarta NaN


def _set(rec, key, val):
    n = _num(val)
    if n is not None:
        rec[key] = n


def _local(ts, offset):
    """ISO en UTC ('...Z') + offset ('+02:00') -> datetime en hora local."""
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    off = offset or "+00:00"
    sign = -1 if off.startswith("-") else 1
    tz = timezone(sign * timedelta(hours=int(off[1:3]), minutes=int(off[4:6])))
    return dt.astimezone(tz)


def _bed_day(dt):
    """Día al que pertenece la hora de dormir (regla del mediodía: antes de las
    12:00 cuenta como el día anterior)."""
    d = dt.date()
    if dt.hour < 12:
        d -= timedelta(days=1)
    return d.isoformat()


def _build(data):
    """Convierte las respuestas crudas en {fecha: campos} + filas de workout.

    Alineación (igual que el import de CSV): recovery/strain/sueño -> fecha de
    DESPERTAR (fin del sueño); hora de dormir -> día en que te acostaste;
    workouts/siestas -> su propia fecha de inicio.
    """
    by_date = defaultdict(dict)
    sleeps_by_id = {s.get("id"): s for s in data.get("sleeps", [])}
    cycles_by_id = {c.get("id"): c for c in data.get("cycles", [])}

    for rec in data.get("recoveries", []):
        slp = sleeps_by_id.get(rec.get("sleep_id"))
        if not slp:
            continue
        off = slp.get("timezone_offset")
        wake = _local(slp.get("end"), off)
        if wake is None:
            continue
        r = by_date[wake.date().isoformat()]
        sc = rec.get("score") or {}
        _set(r, "recovery", sc.get("recovery_score"))
        _set(r, "rhr", sc.get("resting_heart_rate"))
        _set(r, "hrv", sc.get("hrv_rmssd_milli"))
        _set(r, "spo2", sc.get("spo2_percentage"))
        _set(r, "skin_temp", sc.get("skin_temp_celsius"))
        cyc = cycles_by_id.get(rec.get("cycle_id"))
        if cyc:
            csc = cyc.get("score") or {}
            _set(r, "strain", csc.get("strain"))
            kj = _num(csc.get("kilojoule"))     # gasto energético total del día
            if kj is not None:
                r["calories_burned"] = round(kj / 4.184)   # kJ -> kcal
        ssc = slp.get("score") or {}
        stg = ssc.get("stage_summary") or {}
        asleep = ((stg.get("total_light_sleep_time_milli") or 0)
                  + (stg.get("total_slow_wave_sleep_time_milli") or 0)
                  + (stg.get("total_rem_sleep_time_milli") or 0))
        if asleep:
            r["sleep_hours"] = round(asleep / 3600000, 2)
        _set(r, "sleep_performance", ssc.get("sleep_performance_percentage"))
        _set(r, "resp_rate", ssc.get("respiratory_rate"))
        onset = _local(slp.get("start"), off)
        if onset is not None:
            clock = onset.strftime("%H:%M")
            bd = by_date[_bed_day(onset)]
            bd["hora_dormir"] = clock
            bd["hora_dormir_num"] = db.bedtime_to_num(clock)

    for slp in data.get("sleeps", []):
        if slp.get("nap"):
            onset = _local(slp.get("start"), slp.get("timezone_offset"))
            if onset is not None:
                by_date[onset.date().isoformat()]["siesta"] = 1

    agg = defaultdict(lambda: {"min": 0.0, "cal": 0.0, "hr_sum": 0.0, "max": 0.0,
                               "z": [0.0] * 5, "acts": [], "count": 0,
                               "morning": False})
    workout_rows = []
    for w in data.get("workouts", []):
        off = w.get("timezone_offset")
        ws = _local(w.get("start"), off)
        we = _local(w.get("end"), off)
        if ws is None:
            continue
        d = ws.date().isoformat()
        dur = round((we - ws).total_seconds() / 60, 1) if we else 0.0
        sc = w.get("score") or {}
        zd = sc.get("zone_durations") or {}
        zmin = [round((zd.get(f"zone_{n}_milli") or 0) / 60000, 1)
                for n in ("one", "two", "three", "four", "five")]
        cal = (_num(sc.get("kilojoule")) or 0.0) / 4.184       # kJ -> kcal
        avg = _num(sc.get("average_heart_rate")) or 0.0
        name = (w.get("sport_name") or "").strip()
        a = agg[d]
        a["min"] += dur
        a["cal"] += cal
        a["hr_sum"] += avg * dur
        a["max"] = max(a["max"], _num(sc.get("max_heart_rate")) or 0.0)
        a["count"] += 1
        a["morning"] = a["morning"] or ws.hour < 12
        for i in range(5):
            a["z"][i] += zmin[i]
        if name and name not in a["acts"]:
            a["acts"].append(name)
        workout_rows.append({
            "date": d, "start": ws.strftime("%H:%M"), "activity": name,
            "duration_min": dur, "calories": round(cal) if cal else None,
            "avg_hr": avg or None, "max_hr": _num(sc.get("max_heart_rate")),
            "strain": _num(sc.get("strain")),
            **{f"z{i+1}_min": zmin[i] for i in range(5)},
        })
    for d, a in agg.items():
        r = by_date[d]
        r["workout_min"] = round(a["min"], 1)
        r["workout_calories"] = round(a["cal"])
        r["workout_avg_hr"] = round(a["hr_sum"] / a["min"]) if a["min"] else None
        r["workout_max_hr"] = a["max"] or None
        r["workout_count"] = a["count"]
        r["entreno_manana"] = int(a["morning"])
        r["activities"] = ", ".join(a["acts"])
        for i in range(5):
            r[f"hr_zone{i+1}_min"] = round(a["z"][i], 1)

    return by_date, workout_rows


def sync(token, days=30):
    """Descarga los últimos `days` días y los vuelca a la BD (FUSIÓN: no borra
    el historial ni tus campos manuales; solo reescribe los workouts de las
    fechas sincronizadas para no duplicar)."""
    by_date, workout_rows = _build(fetch_recent(token, days))
    db.set_meta("seeded", "1")
    db.set_meta("data_source", "whoop")
    for d in {w["date"] for w in workout_rows}:
        db.delete_workouts_on(d)
    for w in workout_rows:
        db.insert_workout(w)
    for d, rec in by_date.items():
        db.upsert_day(d, rec)
    db.set_meta("whoop_last_sync", datetime.now().strftime("%Y-%m-%d %H:%M"))
    return {"dias": len(by_date), "workouts": len(workout_rows)}
