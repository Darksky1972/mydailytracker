"""Señal — personal habit ↔ biometrics correlation tracker (Phase 1).

Run with:  streamlit run app.py
"""
import calendar
import secrets
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis
import db
import whoop_api
import whoop_import

st.set_page_config(page_title="Daily Tracker", page_icon="📅", layout="wide")

# --- bootstrap: schema + first-run data ------------------------------------
# The SQLite DB (senal.db) persists across restarts and code changes. On a fresh
# DB we load the real Whoop CSVs from ./data if present. So dropping your export
# in ./data once means the app rebuilds your real data automatically even if
# senal.db is ever deleted — no need to re-upload.
DATA_DIR = Path(__file__).parent / "data"
db.init_db()
if db.get_meta("seeded") != "1":
    whoop_import.import_from_folder(DATA_DIR)
    db.set_meta("seeded", "1")

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()

# --- idioma (botón junto al título para cambiar ES ⇄ EN) --------------------
# Solo se traduce la INTERFAZ: lo que escribes tú (comidas, tareas…) se muestra
# tal cual. Las claves del diccionario son el texto original en español.
LANG = st.session_state.get("lang", "es")

_EN = {
    # genérico
    "Hoy": "Today", "Ayer": "Yesterday", "hoy": "today",
    "Guardado": "Saved", "día": "day", "días": "days",
    # barra lateral
    "Datos": "Data",
    "Días registrados": "Days recorded",
    "🗑️ Borrar todo": "🗑️ Delete everything",
    "Aún sin configurar. Pon tus credenciales en "
    "`.streamlit/secrets.toml` (sección `[whoop]`) para conectar.":
        "Not set up yet. Put your credentials in "
        "`.streamlit/secrets.toml` (section `[whoop]`) to connect.",
    "✅ Whoop conectado.": "✅ Whoop connected.",
    "No se pudo conectar": "Could not connect",
    "✅ Conectado a Whoop": "✅ Connected to Whoop",
    "Última sincronización": "Last sync",
    "Días a sincronizar": "Days to sync",
    "La 1ª vez pon un número grande (p. ej. 365) "
    "para traer histórico; luego 7-30 basta.":
        "The first time use a big number (e.g. 365) to pull your history; "
        "afterwards 7-30 is enough.",
    "🔄 Sincronizar ahora": "🔄 Sync now",
    "Sincronizado: {d} días, {w} actividades.": "Synced: {d} days, {w} workouts.",
    "Error al sincronizar": "Sync error",
    "🔍 Ver datos en crudo (depurar)": "🔍 View raw data (debug)",
    "Probar conexión": "Test connection",
    "Desconectar Whoop": "Disconnect Whoop",
    "🔗 Conectar con Whoop": "🔗 Connect with Whoop",
    "Te lleva a Whoop para autorizar y vuelve aquí.":
        "Takes you to Whoop to authorize and brings you back here.",
    "Importar Whoop (CSV)": "Import Whoop (CSV)",
    "Alternativa manual: sube tu export de Whoop (uno o varios CSV).":
        "Manual alternative: upload your Whoop export (one or more CSVs).",
    "⬆️ Importar CSV subidos": "⬆️ Import uploaded CSVs",
    "Sube al menos un CSV primero.": "Upload at least one CSV first.",
    "Importado: {d} días, {w} actividades.": "Imported: {d} days, {w} workouts.",
    "📂 Importar desde /data": "📂 Import from /data",
    "Lee los CSV de Whoop guardados en la carpeta ./data":
        "Reads the Whoop CSVs stored in the ./data folder",
    "No encontré CSV de Whoop en ./data.": "No Whoop CSVs found in ./data.",
    "💾 Los datos se guardan en `senal.db` y persisten entre cambios. "
    "Al reimportar se conservan tus datos manuales (Japonés, Pantalla "
    "noche, Pasos, tareas).":
        "💾 Data is stored in `senal.db` and persists across changes. "
        "Re-importing keeps your manual data (Japanese, Night screen, "
        "Steps, tasks).",
    # hoy
    "Registra tus hábitos y biometría, y explora qué mueve de verdad tu recovery.":
        "Log your habits and biometrics, and explore what really moves your recovery.",
    "Strain (ayer)": "Strain (yesterday)",
    "Sueño (h)": "Sleep (h)",
    # hábitos
    "Rellenar": "Fill in",
    "Cambia a «Ayer» si se te pasó registrar algún hábito.":
        "Switch to “Yesterday” if you forgot to log a habit.",
    "Hábitos": "Habits",
    "Márcalo si NO has hecho «Fap» ese día.": "Check it if you did NOT “Fap” that day.",
    "➕ Mostrar más": "➕ Show more",
    "Minutos de pantalla de ESA noche. Si se te pasó, "
    "cambia a «Ayer» y ponlo en el día que toca.":
        "Screen minutes for THAT night. If you missed it, "
        "switch to “Yesterday” and log it on the right day.",
    "Pasos del día. Apúntalos en su día (usa «Ayer» si "
    "los miras a la mañana siguiente desde la app de Whoop).":
        "Steps for the day. Log them on their day (use “Yesterday” if "
        "you check them the next morning in the Whoop app).",
    "💾 Guardar": "💾 Save",
    # NoFap
    "Mes anterior": "Previous month",
    "Mes siguiente": "Next month",
    "Días tachados = NoFap. En": "Crossed-out days = NoFap. In",
    # tareas
    "Tareas de hoy": "Today's tasks",
    "Prioridad": "Priority",
    "🔴 Alta": "🔴 High", "🟡 Media": "🟡 Medium", "🟢 Baja": "🟢 Low",
    "Eliminar tarea": "Delete task",
    "Nueva tarea": "New task",
    "Añadir tarea…": "Add a task…",
    "Tareas completadas": "Tasks completed",
    "Ponderado por prioridad: 🔴 Alta ×3 · 🟡 Media ×2 · 🟢 Baja ×1.":
        "Weighted by priority: 🔴 High ×3 · 🟡 Medium ×2 · 🟢 Low ×1.",
    "Tareas para mañana": "Tasks for tomorrow",
    "Se planifican para el {d}. Mañana aparecerán en «Tareas de hoy».":
        "Planned for {d}. Tomorrow they will show up under “Today's tasks”.",
    "Nueva tarea mañana": "New task for tomorrow",
    "Añadir tarea para mañana…": "Add a task for tomorrow…",
    # calorías
    "🍽️ Calorías": "🍽️ Calories",
    "Registrar": "Log", "Días pasados": "Past days",
    "Comidas guardadas": "Saved meals",
    "◀ Anterior": "◀ Previous", "Siguiente ▶": "Next ▶",
    "Añadir comida guardada": "Add a saved meal",
    "Comida guardada…": "Saved meal…",
    "Tipo": "Type", "➕ Añadir": "➕ Add",
    "Añadir comida": "Add meal",
    "Comida": "Meal",          # el TIPO «Comida» se traduce con meal_label
    "Tipo de comida": "Meal type",
    "Prot (g)": "Protein (g)", "Grasa (g)": "Fat (g)",
    "p. ej. Pollo con arroz": "e.g. Chicken with rice",
    "p. ej. Tortilla francesa": "e.g. French omelette",
    "Guardar también como comida recurrente": "Also save as a recurring meal",
    "➕ Añadir comida": "➕ Add meal",
    "{k} kcal · P {p} · C {c} · G {g}": "{k} kcal · P {p} · C {c} · F {g}",
    "Eliminar comida": "Delete meal",
    "Diferencia": "Difference", "Quemadas": "Burned", "Consumidas": "Consumed",
    "Proteínas": "Protein", "Carbohidratos": "Carbs", "Grasas": "Fat",
    "déficit": "deficit", "superávit": "surplus",
    "Quemadas − consumidas. Positivo = déficit (gastas más de lo que comes).":
        "Burned − consumed. Positive = deficit (you burn more than you eat).",
    "De Whoop (gasto total del día).": "From Whoop (total daily burn).",
    "Necesita el dato de calorías quemadas de Whoop.":
        "Needs the calories-burned figure from Whoop.",
    "Sin dato de calorías quemadas de Whoop para este día. "
    "Sincroniza Whoop (o reimporta los CSV) para ver el balance.":
        "No Whoop calories-burned data for this day. "
        "Sync Whoop (or re-import the CSVs) to see the balance.",
    "Aún no has registrado comidas. Empieza en la pestaña «Registrar».":
        "You haven't logged any meals yet. Start in the “Log” tab.",
    "Día": "Day", "Quemadas (Whoop)": "Burned (Whoop)",
    "Diferencia = quemadas − consumidas. Positivo = déficit calórico.":
        "Difference = burned − consumed. Positive = calorie deficit.",
    "Evolución: quemadas vs consumidas": "Trend: burned vs consumed",
    "Media global": "All-time average",
    "🟢 área verde = quemas más (déficit) · 🔴 roja = comes más. "
    "Las verticales punteadas marcan huecos de días sin datos. "
    "La línea gris discontinua es el punto medio entre las medias "
    "globales de quemadas y consumidas.":
        "🟢 green area = you burn more (deficit) · 🔴 red = you eat more. "
        "Dotted verticals mark gaps of days without data. The grey dashed "
        "line is the midpoint between the all-time averages of burned "
        "and consumed.",
    "Comidas que repites a menudo. Guárdalas aquí y añádelas con un clic "
    "desde la pestaña «Registrar».":
        "Meals you repeat often. Save them here and add them with one "
        "click from the “Log” tab.",
    "💾 Guardar comida": "💾 Save meal",
    "Todavía no hay comidas guardadas.": "No saved meals yet.",
    "Eliminar comida guardada": "Delete saved meal",
    # calendario de balance
    "🟢 déficit > 200 · 🟡 entre −200 y 200 · 🔴 superávit > 200 kcal. "
    "Solo se colorean los días con comidas y dato de Whoop. "
    "Pincha un día para editar sus comidas.":
        "🟢 deficit > 200 · 🟡 between −200 and 200 · 🔴 surplus > 200 kcal. "
        "Only days with meals and Whoop data are coloured. "
        "Click a day to edit its meals.",
    "Editar comidas de este día": "Edit meals for this day",
    "Media · últimos 30 días": "Average · last 30 days",
    "Media · global": "Average · all time",
    "Aún no hay días con comidas y dato de Whoop.":
        "No days with meals and Whoop data yet.",
    "Sobre": "Across",
    "con comidas y dato de Whoop (sin contar hoy). En kcal.":
        "with meals and Whoop data (not counting today). In kcal.",
    # actividad
    "Actividad de hoy": "Today's activity",
    "Tiempo total": "Total time", "Calorías": "Calories", "FC media": "Avg HR",
    "Minutos por zona de FC": "Minutes per HR zone",
    "Actividad": "Activity", "máx": "max",
    "No hay actividades registradas hoy. Importa tu export de Whoop "
    "desde la barra lateral.":
        "No activities recorded today. Import your Whoop export "
        "from the sidebar.",
    # análisis
    "Análisis": "Analysis",
    "Lag +1 día  ·  hábito de hoy → biometría de mañana":
        "Lag +1 day  ·  today's habit → tomorrow's biometrics",
    "Recovery, HRV, RHR y sueño se miden por la mañana y reflejan la noche "
    "anterior, así que con el lag se emparejan hábito[día] con whoop[día+1]. "
    "El Strain se acumula durante el día, así que SIEMPRE es del mismo día (no "
    "se desplaza con el lag). Los datos manuales (incl. Pantalla noche y Pasos) "
    "se registran en su día real, así que tampoco se desplazan.":
        "Recovery, HRV, RHR and sleep are measured in the morning and reflect "
        "the previous night, so with the lag habit[day] pairs with whoop[day+1]. "
        "Strain accumulates DURING the day, so it is ALWAYS same-day (the lag "
        "never shifts it). Manual inputs (incl. Night screen and Steps) are "
        "logged on their real day, so they don't shift either.",
    "──────── booleanas (0/1) ────────": "──────── boolean (0/1) ────────",
    "──────── numéricas ────────": "──────── numeric ────────",
    "Fuerza": "Strength",
    "n (días emparejados)": "n (paired days)",
    "⚠️ Solo {n} días emparejados. Con n < 30 los resultados pueden ser "
    "ruido — no saques conclusiones todavía.":
        "⚠️ Only {n} paired days. With n < 30 the results can be noise — "
        "don't draw conclusions yet.",
    "nula": "none",
    "débil positiva": "weak positive", "débil negativa": "weak negative",
    "moderada positiva": "moderate positive",
    "moderada negativa": "moderate negative",
    "fuerte positiva": "strong positive", "fuerte negativa": "strong negative",
    "reciente →": "recent →",
    "Elige dos variables distintas con datos suficientes para ver el scatter.":
        "Pick two different variables with enough data to see the scatter plot.",
    "Matriz de correlaciones (exploratoria)": "Correlation matrix (exploratory)",
    "Hábitos y actividad (filas) × métricas Whoop (columnas). Es **exploratoria**: "
    "son muchas pruebas simultáneas, así que algunas celdas parecerán fuertes por "
    "puro azar. No implica causalidad. (Rojo = negativa, azul = positiva.)":
        "Habits and activity (rows) × Whoop metrics (columns). It is "
        "**exploratory**: many simultaneous tests, so some cells will look "
        "strong by pure chance. It does not imply causation. "
        "(Red = negative, blue = positive.)",
    "Mostrar todas las variables": "Show all variables",
    "No hay variables con suficientes datos (≥30 días emparejados) para la matriz.":
        "No variables with enough data (≥30 paired days) for the matrix.",
    "Por defecto se ocultan Siesta, Horas de sueño, Rendimiento sueño, "
    "Frec. respiratoria, Temp. piel y SpO₂ para que la matriz sea más legible. "
    "Actívalo para verlas todas.":
        "By default Nap, Sleep hours, Sleep performance, Respiratory rate, "
        "Skin temp and SpO₂ are hidden to keep the matrix readable. "
        "Turn it on to see them all.",
    "Pista: prueba X = «Hora de dormir», Y = «Recovery». Con el lag activado "
    "debería aparecer una relación; al desactivarlo, desaparece.":
        "Tip: try X = “Bedtime”, Y = “Recovery”. With the lag ON a relationship "
        "should appear; switch it off and it disappears.",
}


def T(s):
    """Texto de interfaz, traducido si el idioma activo es inglés."""
    return _EN.get(s, s) if LANG == "en" else s


# Etiquetas de las variables (hábitos/whoop) en inglés.
LABELS_EN = {
    "entreno_manana": "Morning workout",
    "estiramientos": "Stretching",
    "journaling": "Journaling",
    "leer": "Read in bed",
    "fap": "Fap",
    "beber_agua": "Drink water",
    "cafeina": "Caffeine",
    "alcohol": "Alcohol",
    "comer_restaurante": "Eat at a restaurant",
    "siesta": "Nap",
    "japones_min": "Japanese (min)",
    "pantalla_noche_min": "Night screen (min)",
    "pasos": "Steps",
    "hora_dormir_num": "Bedtime",
    "tareas_pct": "Tasks completed (%)",
    "workout_min": "Activity (min)",
    "workout_calories": "Activity calories",
    "workout_avg_hr": "Activity avg HR",
    "sleep_hours": "Sleep hours",
    "sleep_performance": "Sleep performance (%)",
    "resp_rate": "Respiratory rate",
    "skin_temp": "Skin temp (°C)",
}

# Tipos de comida: en la BD se guardan SIEMPRE en español; esto solo cambia
# cómo se muestran.
MEAL_TYPES_EN = {"Desayuno": "Breakfast", "Comida": "Lunch",
                 "Merienda": "Snack", "Cena": "Dinner", "Sin tipo": "No type"}


def meal_label(t):
    return MEAL_TYPES_EN.get(t, t) if LANG == "en" else t


def label(v):
    if LANG == "en" and v in LABELS_EN:
        return LABELS_EN[v]
    return db.LABELS.get(v, v)


def default(d, key, fallback):
    """Stored value for `key`, or `fallback` when it's missing/NULL.
    (Avoids the `x or fallback` trap where a real 0 would be replaced.)"""
    val = d.get(key)
    return fallback if val is None else val


def fmt_num(x):
    """Número sin decimales innecesarios: 500.0 → '500', 12.5 → '12.5'."""
    return f"{(x or 0):.1f}".rstrip("0").rstrip(".")


def render_avg_block(title, rows):
    """Muestra la media de quemadas/consumidas/diferencia (en kcal) de una lista de
    tuplas (quemadas, consumidas). `rows` ya viene filtrada a días con ambos datos."""
    st.markdown(f"**{title}**")
    if not rows:
        st.caption(T("Aún no hay días con comidas y dato de Whoop."))
        return
    n = len(rows)
    ab = sum(b for b, _ in rows) / n
    ac = sum(c for _, c in rows) / n
    ad = ab - ac
    cols = st.columns(3)
    cols[0].metric(T("Quemadas"), f"{ab:.0f}")
    cols[1].metric(T("Consumidas"), f"{ac:.0f}")
    cols[2].metric(T("Diferencia"), f"{ad:+.0f}",
                   delta=T("déficit") if ad >= 0 else T("superávit"), delta_color="off")
    _dw = T("día") if n == 1 else T("días")
    st.caption(f"{T('Sobre')} {n} {_dw} "
               f"{T('con comidas y dato de Whoop (sin contar hoy). En kcal.')}")


# Prioridad de tareas (el número es el peso: la barra de completadas pondera por él).
PRIO_ORDER = [3, 2, 1]                                    # alta → baja (orden del selector)
PRIO_LABELS = {3: "🔴 Alta", 2: "🟡 Media", 1: "🟢 Baja"}
PRIO_EMOJI = {3: "🔴", 2: "🟡", 1: "🟢"}


# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------
STRAIN_COLOR = "#3498db"          # azul, a petición
TRACK_COLOR = "rgba(150,150,150,0.18)"   # arco no rellenado
GREEN, AMBER, RED = "#2ecc71", "#f1c40f", "#e74c3c"


def _band_color(v, good, ok, higher_better=True):
    """Verde / ámbar / rojo según dos umbrales. `higher_better=False` invierte
    (menos es mejor, p. ej. RHR). None → color de arco vacío."""
    if v is None:
        return TRACK_COLOR
    if higher_better:
        return GREEN if v >= good else AMBER if v >= ok else RED
    return GREEN if v < good else AMBER if v <= ok else RED


def ring(value, title, lo, hi, color, decimals=0):
    """Full-circle ring filled by where `value` cae entre `lo` (vacío) y `hi`
    (lleno). Si hi < lo se invierte (menos = más lleno), p. ej. RHR 100→50."""
    v = 0.0 if value is None else float(value)
    frac = 0.0 if hi == lo else (v - lo) / (hi - lo)
    frac = max(0.0, min(1.0, frac))
    fig = go.Figure(go.Pie(
        values=[frac, 1 - frac],
        hole=0.72,
        sort=False,
        direction="clockwise",
        rotation=0,
        marker=dict(colors=[color, TRACK_COLOR], line=dict(width=0)),
        textinfo="none",
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=230, margin=dict(l=10, r=10, t=55, b=10),
        annotations=[dict(text=f"<b>{v:.{decimals}f}</b>", x=0.5, y=0.5,
                          showarrow=False, font=dict(size=30))],
    )
    return fig


def _is_dark():
    """True when the browser/app is in dark mode (best-effort, never raises)."""
    try:
        t = getattr(st.context.theme, "type", None)
        if t:
            return str(t).lower() == "dark"
    except Exception:
        pass
    try:
        return str(st.get_option("theme.base")).lower() == "dark"
    except Exception:
        return False


def _fg():
    """Foreground/text colour that reads on the active theme."""
    return "#e6e6e6" if _is_dark() else "#31333F"


# --- NoFap calendar --------------------------------------------------------
_MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
              "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
_WEEKDAYS_ES = ["L", "M", "X", "J", "V", "S", "D"]
_WEEKDAYS_EN = ["M", "T", "W", "T", "F", "S", "S"]
_MONTHS = _MONTHS_EN if LANG == "en" else _MONTHS_ES
_WEEKDAYS = _WEEKDAYS_EN if LANG == "en" else _WEEKDAYS_ES
_NOFAP_CROSS = "#2ecc71"   # color de la ✗ de NoFap (verde = día logrado)


def nofap_calendar_html(year, month, nofap_dates, today):
    """Mini-calendario HTML del mes: marca con ✗ los días de NoFap (fap == 0).

    Usa table-layout:fixed + ancho 1/7 por columna para que las 7 columnas sean
    idénticas en todos los meses (en modo auto se ajustarían al contenido).
    """
    fg = _fg()
    head = "".join(
        f"<th style='width:14.28%;padding:3px;font-size:11px;color:{fg};"
        f"opacity:.55;'>{d}</th>" for d in _WEEKDAYS)
    rows = ""
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        cells = ""
        for d in week:
            if d == 0:
                cells += "<td></td>"
                continue
            the_date = date(year, month, d)
            style = (f"text-align:center;padding:5px 0;font-size:12px;color:{fg};"
                     "border-radius:6px;")
            if the_date == today:
                style += "background:rgba(52,152,219,0.18);font-weight:700;"
            if the_date in nofap_dates:
                # número atenuado con una ✗ verde superpuesta encima.
                num = (f"<span style='position:relative;display:inline-block;"
                       f"min-width:16px;'><span style='opacity:.4;'>{d}</span>"
                       f"<span style='position:absolute;left:0;right:0;top:50%;"
                       f"transform:translateY(-50%);color:{_NOFAP_CROSS};"
                       f"font-weight:700;font-size:16px;'>✗</span></span>")
            else:
                num = str(d)
            cells += f"<td style='{style}'>{num}</td>"
        rows += f"<tr>{cells}</tr>"
    return (f"<table style='width:100%;table-layout:fixed;border-collapse:collapse;'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")


# --- comidas + calendario de balance calórico ------------------------------
MEAL_TYPES = ["Desayuno", "Comida", "Merienda", "Cena"]
MEAL_TYPE_EMOJI = {"Desayuno": "🌅", "Comida": "🍽️", "Merienda": "🍎", "Cena": "🌙"}
_CAL_GREEN = "rgba(46,204,113,0.55)"     # déficit  (quemas > comes)
_CAL_AMBER = "rgba(241,196,15,0.55)"     # equilibrio (±200)
_CAL_RED = "rgba(231,76,60,0.55)"        # superávit (comes > quemas)


def _cal_diff_color(diff):
    """Color del día por su balance (quemadas − consumidas)."""
    if diff > 200:
        return _CAL_GREEN
    if diff < -200:
        return _CAL_RED
    return _CAL_AMBER


def calorie_calendar_html(year, month, diffs, today):
    """Mini-calendario que colorea cada día según su balance calórico:
    verde = déficit > 200, amarillo = ±200, rojo = superávit > 200.
    `diffs`: {date: quemadas − consumidas} (solo días con ambos datos)."""
    fg = _fg()
    head = "".join(
        f"<th style='width:14.28%;padding:3px;font-size:11px;color:{fg};"
        f"opacity:.55;'>{d}</th>" for d in _WEEKDAYS)
    rows = ""
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        cells = ""
        for d in week:
            if d == 0:
                cells += "<td></td>"
                continue
            the_date = date(year, month, d)
            style = f"text-align:center;font-size:12px;color:{fg};border-radius:6px;"
            if the_date in diffs:
                style += f"background:{_cal_diff_color(diffs[the_date])};font-weight:700;"
            if the_date == today:
                style += "outline:2px solid rgba(52,152,219,0.7);"
            # Días pasados/hoy = enlace que salta a ese día en la pestaña Registrar.
            if the_date <= today:
                inner = (f"<a href='?meal_day={the_date.isoformat()}' target='_self' "
                         f"title='{T('Editar comidas de este día')}' style='color:inherit;"
                         f"text-decoration:none;display:block;padding:5px 0;'>{d}</a>")
            else:
                inner = f"<div style='padding:5px 0;'>{d}</div>"
            cells += f"<td style='{style}'>{inner}</td>"
        rows += f"<tr>{cells}</tr>"
    return (f"<table style='width:100%;table-layout:fixed;border-collapse:collapse;'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")


# ---------------------------------------------------------------------------
# Sidebar — data management
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header(T("Datos"))
    st.metric(T("Días registrados"), db.count_days())
    if st.button(T("🗑️ Borrar todo"), width="stretch"):
        db.clear_all()
        st.rerun()

    # --- Whoop API (conectar + sincronizar) ---
    st.divider()
    st.subheader("Whoop (API)")
    try:
        _wsec = dict(st.secrets["whoop"])
    except Exception:
        _wsec = None

    if not _wsec:
        st.caption(T("Aún sin configurar. Pon tus credenciales en "
                     "`.streamlit/secrets.toml` (sección `[whoop]`) para conectar."))
    else:
        # ¿Volvemos de autorizar? Whoop redirige con ?code=...
        _code = st.query_params.get("code")
        if _code and not whoop_api.is_connected():
            try:
                whoop_api.exchange_code(_code, _wsec["client_id"],
                                        _wsec["client_secret"], _wsec["redirect_uri"])
                st.query_params.clear()
                st.success(T("✅ Whoop conectado."))
                st.rerun()
            except Exception as e:
                st.error(f"{T('No se pudo conectar')}: {e}")

        if whoop_api.is_connected():
            st.success(T("✅ Conectado a Whoop"))
            _last = db.get_meta("whoop_last_sync")
            if _last:
                st.caption(f"{T('Última sincronización')}: {_last}")
            _days = st.number_input(T("Días a sincronizar"), 1, 730, 30, step=1,
                                    help=T("La 1ª vez pon un número grande (p. ej. 365) "
                                           "para traer histórico; luego 7-30 basta."))
            if st.button(T("🔄 Sincronizar ahora"), width="stretch"):
                try:
                    _tok = whoop_api.access_token(_wsec["client_id"], _wsec["client_secret"])
                    _res = whoop_api.sync(_tok, days=int(_days))
                    st.success(T("Sincronizado: {d} días, {w} actividades.")
                               .format(d=_res["dias"], w=_res["workouts"]))
                    st.rerun()
                except Exception as e:
                    st.error(f"{T('Error al sincronizar')}: {e}")
            with st.expander(T("🔍 Ver datos en crudo (depurar)")):
                if st.button(T("Probar conexión"), key="whoop_probe", width="stretch"):
                    try:
                        _tok = whoop_api.access_token(_wsec["client_id"],
                                                      _wsec["client_secret"])
                        _data = whoop_api.fetch_recent(_tok, days=14)
                        st.write({k: len(v) for k, v in _data.items()})
                    except Exception as e:
                        st.error(f"Error: {e}")
            if st.button(T("Desconectar Whoop"), width="stretch"):
                whoop_api.disconnect()
                st.rerun()
        else:
            _url = whoop_api.authorize_url(_wsec["client_id"], _wsec["redirect_uri"],
                                           secrets.token_urlsafe(16))
            st.link_button(T("🔗 Conectar con Whoop"), _url, width="stretch")
            st.caption(T("Te lleva a Whoop para autorizar y vuelve aquí."))

    st.divider()
    st.subheader(T("Importar Whoop (CSV)"))
    st.caption(T("Alternativa manual: sube tu export de Whoop (uno o varios CSV)."))
    up_phys = st.file_uploader("physiological_cycles.csv", type="csv", key="up_phys")
    up_work = st.file_uploader("workouts.csv", type="csv", key="up_work")
    up_jour = st.file_uploader("journal_entries.csv", type="csv", key="up_jour")
    up_sleep = st.file_uploader("sleeps.csv", type="csv", key="up_sleep")
    if st.button(T("⬆️ Importar CSV subidos"), width="stretch"):
        if not any([up_phys, up_work, up_jour, up_sleep]):
            st.warning(T("Sube al menos un CSV primero."))
        else:
            s = whoop_import.import_whoop(up_phys, up_jour, up_work, up_sleep)
            st.success(T("Importado: {d} días, {w} actividades.")
                       .format(d=s["days"], w=s["workouts"]))
            st.rerun()
    if st.button(T("📂 Importar desde /data"), width="stretch",
                 help=T("Lee los CSV de Whoop guardados en la carpeta ./data")):
        s = whoop_import.import_from_folder(DATA_DIR)
        if not s:
            st.warning(T("No encontré CSV de Whoop en ./data."))
        else:
            st.success(T("Importado: {d} días, {w} actividades.")
                       .format(d=s["days"], w=s["workouts"]))
            st.rerun()
    st.caption(T("💾 Los datos se guardan en `senal.db` y persisten entre cambios. "
                 "Al reimportar se conservan tus datos manuales (Japonés, Pantalla "
                 "noche, Pasos, tareas)."))


# ---------------------------------------------------------------------------
# HOY
# ---------------------------------------------------------------------------
_tt, _tl = st.columns([0.82, 0.18])
_tt.title("📅 Daily Tracker")
with _tl:
    st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)
    if st.button("🇬🇧 English" if LANG == "es" else "🇪🇸 Español",
                 key="lang_btn", width="stretch"):
        st.session_state.lang = "en" if LANG == "es" else "es"
        st.rerun()
st.caption(T("Registra tus hábitos y biometría, y explora qué mueve de verdad tu recovery."))

st.header(T("Hoy"))
st.subheader(TODAY)

day = db.get_day(TODAY) or {}
yday = db.get_day(YESTERDAY) or {}   # para el Strain de ayer (valor ya cerrado)
# Todos los días, cargados una sola vez (para el calendario NoFap y el análisis).
df = db.load_days_df()

# --- Whoop rings (read-only; filled by the Whoop CSV import) ---
g = st.columns(5)
g[0].plotly_chart(ring(day.get("recovery"), "Recovery", 0, 100,
                       _band_color(day.get("recovery"), 67, 34)), width="stretch")
g[1].plotly_chart(ring(day.get("hrv"), "HRV (ms)", 20, 60,
                       _band_color(day.get("hrv"), 47, 33)), width="stretch")
g[2].plotly_chart(ring(yday.get("strain"), T("Strain (ayer)"), 0, 21, STRAIN_COLOR,
                       decimals=1), width="stretch")
g[3].plotly_chart(ring(day.get("rhr"), "RHR (ppm)", 100, 50,
                       _band_color(day.get("rhr"), 65, 75, higher_better=False)), width="stretch")
g[4].plotly_chart(ring(day.get("sleep_hours"), T("Sueño (h)"), 0, 9,
                       _band_color(day.get("sleep_hours"), 7.5, 6.5), decimals=1), width="stretch")

# --- habit logger (izq.) + calendario NoFap (dcha.) ---
log_col, cal_col = st.columns([0.62, 0.38])
with log_col:
    st.markdown(
        "<style>div[role='radiogroup'] label{font-size:1.15rem;font-weight:700;}</style>",
        unsafe_allow_html=True)
    _hlabel = st.radio(T("Rellenar"), ["Ayer", "Hoy"], index=1, horizontal=True,
                       format_func=T,
                       help=T("Cambia a «Ayer» si se te pasó registrar algún hábito."))
    habit_date = TODAY if _hlabel == "Hoy" else YESTERDAY
    hday = db.get_day(habit_date) or {}
    _k = habit_date   # sufijo de las keys: al cambiar de día, recarga los valores
    with st.form("logger"):
        st.markdown(f"**{T('Hábitos')} · {habit_date}**")
        h = st.columns(3)
        entreno = h[0].checkbox(label("entreno_manana"), bool(hday.get("entreno_manana")),
                                key=f"hb_entreno_{_k}")
        estir = h[1].checkbox(label("estiramientos"), bool(hday.get("estiramientos")),
                              key=f"hb_estir_{_k}")
        journ = h[2].checkbox(label("journaling"), bool(hday.get("journaling")),
                              key=f"hb_journ_{_k}")
        h2 = st.columns(3)
        leer = h2[0].checkbox(label("leer"), bool(hday.get("leer")), key=f"hb_leer_{_k}")
        # Casilla inversa: marcada = NoFap (no has hecho «Fap» ese día).
        nofap = h2[1].checkbox("NoFap", not bool(hday.get("fap")), key=f"hb_nofap_{_k}",
                               help=T("Márcalo si NO has hecho «Fap» ese día."))
        agua = h2[2].checkbox(label("beber_agua"), bool(hday.get("beber_agua")),
                              key=f"hb_agua_{_k}")

        with st.expander(T("➕ Mostrar más")):
            m = st.columns(3)
            cafeina = m[0].checkbox(label("cafeina"), bool(hday.get("cafeina")),
                                    key=f"hb_caf_{_k}")
            alcohol = m[1].checkbox(label("alcohol"), bool(hday.get("alcohol")),
                                    key=f"hb_alc_{_k}")
            restaurante = m[2].checkbox(label("comer_restaurante"),
                                        bool(hday.get("comer_restaurante")),
                                        key=f"hb_rest_{_k}")

        n1, n2, n3 = st.columns(3)
        japones = n1.slider(label("japones_min"), 0, 120,
                            min(int(default(hday, "japones_min", 0)), 120),
                            key=f"hb_jap_{_k}")
        pantalla = n2.slider(label("pantalla_noche_min"), 0, 120,
                             min(int(default(hday, "pantalla_noche_min", 0)), 120),
                             key=f"hb_pan_{_k}",
                             help=T("Minutos de pantalla de ESA noche. Si se te pasó, "
                                    "cambia a «Ayer» y ponlo en el día que toca."))
        pasos = n3.number_input(label("pasos"), min_value=0, max_value=100000, step=500,
                                value=int(default(hday, "pasos", 0)), key=f"hb_pasos_{_k}",
                                help=T("Pasos del día. Apúntalos en su día (usa «Ayer» si "
                                       "los miras a la mañana siguiente desde la app de Whoop)."))

        saved = st.form_submit_button(T("💾 Guardar"), width="stretch")

with cal_col:
    # Espacio arriba para que el calendario baje y quede a la altura del formulario.
    st.markdown("<div style='height:6rem'></div>", unsafe_allow_html=True)
    _nofap = set()
    if not df.empty and "fap" in df.columns:
        _nofap = set(pd.to_datetime(df.loc[df["fap"] == 0, "date"]).dt.date)

    # Mes mostrado = mes actual + offset (≤ 0; no se permite ir al futuro).
    _off = st.session_state.get("nofap_offset", 0)
    _base = date.today().replace(day=1)
    _y = _base.year + (_base.month - 1 + _off) // 12
    _m = (_base.month - 1 + _off) % 12 + 1

    nav = st.columns([0.16, 0.68, 0.16])
    if nav[0].button("◀", key="nofap_prev", help=T("Mes anterior"), width="stretch"):
        st.session_state.nofap_offset = _off - 1
        st.rerun()
    nav[1].markdown(
        f"<div style='text-align:center;font-weight:600;'>🚫 NoFap · "
        f"{_MONTHS[_m - 1]} {_y}</div>", unsafe_allow_html=True)
    if nav[2].button("▶", key="nofap_next", help=T("Mes siguiente"),
                     width="stretch", disabled=_off >= 0):
        st.session_state.nofap_offset = _off + 1
        st.rerun()

    st.markdown(nofap_calendar_html(_y, _m, _nofap, date.today()),
                unsafe_allow_html=True)
    _n_month = sum(1 for x in _nofap if x.year == _y and x.month == _m)
    st.caption(f"{T('Días tachados = NoFap. En')} {_MONTHS[_m - 1]}: {_n_month}.")

if saved:
    db.upsert_day(habit_date, {
        "entreno_manana": int(entreno),
        "estiramientos": int(estir),
        "journaling": int(journ),
        "leer": int(leer),
        "fap": int(not nofap),   # NoFap marcado → fap = 0
        "beber_agua": int(agua),
        "cafeina": int(cafeina),
        "alcohol": int(alcohol),
        "comer_restaurante": int(restaurante),
        "japones_min": int(japones),
        "pantalla_noche_min": int(pantalla),
        "pasos": int(pasos),
        "tareas_pct": db.tasks_pct(habit_date),
    })
    st.success(f"{T('Guardado')} ({habit_date}) ✅")

# --- tasks (hoy a la izq. · mañana a la dcha.) -----------------------------
hoy_col, manana_col = st.columns(2)

with hoy_col:
    st.markdown(f"### {T('Tareas de hoy')}")
    for t in db.get_tasks(TODAY):
        tc1, tc2, tc3 = st.columns([0.56, 0.32, 0.12])
        checked = tc1.checkbox(t["text"], bool(t["done"]), key=f"task_{t['id']}")
        prio = tc2.selectbox(
            T("Prioridad"), PRIO_ORDER, index=PRIO_ORDER.index(t.get("priority") or 2),
            format_func=lambda p: T(PRIO_LABELS[p]), key=f"prio_{t['id']}",
            label_visibility="collapsed")
        if checked != bool(t["done"]):
            db.set_task_done(t["id"], checked)
            db.upsert_day(TODAY, {"tareas_pct": db.tasks_pct(TODAY)})
            st.rerun()
        if prio != (t.get("priority") or 2):
            db.set_task_priority(t["id"], prio)
            db.upsert_day(TODAY, {"tareas_pct": db.tasks_pct(TODAY)})
            st.rerun()
        if tc3.button("🗑️", key=f"del_{t['id']}", help=T("Eliminar tarea")):
            db.delete_task(t["id"])
            db.upsert_day(TODAY, {"tareas_pct": db.tasks_pct(TODAY)})
            st.rerun()

    with st.form("add_task", clear_on_submit=True):
        ac1, ac2, ac3 = st.columns([0.55, 0.30, 0.15])
        new_task = ac1.text_input(T("Nueva tarea"), label_visibility="collapsed",
                                  placeholder=T("Añadir tarea…"))
        new_prio = ac2.selectbox(T("Prioridad"), PRIO_ORDER, index=1,
                                 format_func=lambda p: T(PRIO_LABELS[p]),
                                 key="prio_add_hoy", label_visibility="collapsed")
        if ac3.form_submit_button("➕", width="stretch") and new_task.strip():
            db.add_task(TODAY, new_task.strip(), new_prio)
            db.upsert_day(TODAY, {"tareas_pct": db.tasks_pct(TODAY)})
            st.rerun()

    pct_today = db.tasks_pct(TODAY)
    st.progress((pct_today or 0) / 100,
                text=f"{T('Tareas completadas')}: {0 if pct_today is None else pct_today:.0f}%")
    st.caption(T("Ponderado por prioridad: 🔴 Alta ×3 · 🟡 Media ×2 · 🟢 Baja ×1."))

with manana_col:
    st.markdown(f"### {T('Tareas para mañana')}")
    st.caption(T("Se planifican para el {d}. Mañana aparecerán en «Tareas de hoy».")
               .format(d=TOMORROW))
    for t in db.get_tasks(TOMORROW):
        mc1, mc2 = st.columns([0.92, 0.08])
        mc1.write(f"{PRIO_EMOJI[t.get('priority') or 2]} {t['text']}")
        if mc2.button("🗑️", key=f"del_tmrw_{t['id']}", help=T("Eliminar tarea")):
            db.delete_task(t["id"])
            st.rerun()

    with st.form("add_task_tmrw", clear_on_submit=True):
        bc1, bc2, bc3 = st.columns([0.55, 0.30, 0.15])
        new_task_t = bc1.text_input(T("Nueva tarea mañana"), label_visibility="collapsed",
                                    placeholder=T("Añadir tarea para mañana…"))
        new_prio_t = bc2.selectbox(T("Prioridad"), PRIO_ORDER, index=1,
                                   format_func=lambda p: T(PRIO_LABELS[p]),
                                   key="prio_add_tmrw", label_visibility="collapsed")
        if bc3.form_submit_button("➕", width="stretch") and new_task_t.strip():
            db.add_task(TOMORROW, new_task_t.strip(), new_prio_t)
            st.rerun()

# --- Calorías / nutrición --------------------------------------------------
st.markdown(f"### {T('🍽️ Calorías')}")
# Si vienes de pinchar un día en el calendario de balance (?meal_day=AAAA-MM-DD),
# salta a ese día en la pestaña Registrar y limpia el parámetro de la URL.
_qd = st.query_params.get("meal_day")
if _qd:
    try:
        st.session_state.meal_day_offset = min(
            0, (date.fromisoformat(_qd) - date.today()).days)
    except ValueError:
        pass
    try:
        del st.query_params["meal_day"]
    except KeyError:
        pass
# Balance por día (quemadas − consumidas) para colorear el calendario de la dcha.
# cal_rows guarda (fecha, quemadas, consumidas) SOLO de días con ambos datos, para
# poder calcular medias del último mes ignorando los días faltantes.
_meals_by_day = db.meals_by_day()
cal_diffs = {}
cal_rows = []
for _d, _v in _meals_by_day.items():
    _dd = db.get_day(_d) or {}
    _bd = _dd.get("calories_burned")
    _cons = _v.get("kcal") or 0
    if _bd:
        _do = date.fromisoformat(_d)
        cal_diffs[_do] = _bd - _cons
        cal_rows.append((_do, _bd, _cons))
# Para las MEDIAS ignoramos hoy: aún no tiene todas las comidas registradas y
# falsearía el resultado. El gráfico y el calendario sí siguen mostrando hoy.
cal_rows_avg = [r for r in cal_rows if r[0] != date.today()]

cal_main, cal_cal = st.columns([0.62, 0.38])

with cal_main:
    cal_reg, cal_hist, cal_db = st.tabs(
        [T("Registrar"), T("Días pasados"), T("Comidas guardadas")])

    # Registrar: añadir comidas (manual o desde plantilla) y ver el balance del día.
    with cal_reg:
        # Día seleccionado mediante botones ◀ / ▶ (offset ≤ 0; no se va al futuro).
        _moff = st.session_state.get("meal_day_offset", 0)
        meal_date = (date.today() + timedelta(days=_moff)).isoformat()
        dnav = st.columns([0.25, 0.5, 0.25])
        if dnav[0].button(T("◀ Anterior"), key="meal_prev", width="stretch"):
            st.session_state.meal_day_offset = _moff - 1
            st.rerun()
        _today_tag = f" · {T('hoy')}" if _moff == 0 else ""
        dnav[1].markdown(
            f"<div style='text-align:center;font-weight:600;padding-top:0.45rem;'>"
            f"{meal_date}{_today_tag}</div>",
            unsafe_allow_html=True)
        if dnav[2].button(T("Siguiente ▶"), key="meal_next", width="stretch",
                          disabled=_moff >= 0):
            st.session_state.meal_day_offset = _moff + 1
            st.rerun()
        presets = db.get_meal_presets()

        # Atajo: añadir una comida guardada con un clic, eligiendo su tipo.
        if presets:
            pc1, pc2, pc3 = st.columns([0.5, 0.28, 0.22])
            _pick = pc1.selectbox(
                T("Añadir comida guardada"), presets,
                format_func=lambda p: f"{p['name']} · {fmt_num(p['kcal'])} kcal",
                key="meal_preset_pick", index=None,
                placeholder=T("Comida guardada…"), label_visibility="collapsed")
            _pick_type = pc2.selectbox(T("Tipo"), MEAL_TYPES, key="meal_preset_type",
                                       format_func=meal_label,
                                       label_visibility="collapsed")
            if pc3.button(T("➕ Añadir"), key="add_from_preset", width="stretch") and _pick:
                db.add_meal(meal_date, _pick["name"], _pick["kcal"], _pick["protein"],
                            _pick["carbs"], _pick["fat"], _pick_type)
                st.rerun()

        # Añadir una comida nueva (tipo + macros).
        with st.form("add_meal", clear_on_submit=True):
            st.markdown(f"**{T('Añadir comida')}**")
            mc = st.columns([0.6, 0.4])
            m_name = mc[0].text_input(T("Comida"), placeholder=T("p. ej. Pollo con arroz"))
            m_type = mc[1].selectbox(T("Tipo de comida"), MEAL_TYPES, key="meal_type_new",
                                     format_func=meal_label)
            mn = st.columns(4)
            m_kcal = mn[0].number_input("kcal", 0.0, 10000.0, step=50.0, format="%.1f")
            m_prot = mn[1].number_input(T("Prot (g)"), 0.0, 1000.0, step=5.0, format="%.1f")
            m_carb = mn[2].number_input("Carbs (g)", 0.0, 1000.0, step=5.0, format="%.1f")
            m_fat = mn[3].number_input(T("Grasa (g)"), 0.0, 1000.0, step=5.0, format="%.1f")
            save_preset = st.checkbox(T("Guardar también como comida recurrente"))
            if st.form_submit_button(T("➕ Añadir comida"), width="stretch") and m_name.strip():
                db.add_meal(meal_date, m_name.strip(), m_kcal, m_prot, m_carb, m_fat, m_type)
                if save_preset:
                    db.add_meal_preset(m_name.strip(), m_kcal, m_prot, m_carb, m_fat)
                st.rerun()

        # Comidas del día, agrupadas por tipo (Desayuno → Cena).
        meals = db.get_meals(meal_date)
        meals.sort(key=lambda m: (MEAL_TYPES.index(m["meal_type"])
                                  if m.get("meal_type") in MEAL_TYPES else 99, m["id"]))
        _last_type = object()
        for m in meals:
            _t = m.get("meal_type") or "Sin tipo"
            if _t != _last_type:
                st.markdown(f"**{MEAL_TYPE_EMOJI.get(_t, '🍴')} {meal_label(_t)}**")
                _last_type = _t
            lc1, lc2, lc3 = st.columns([0.5, 0.42, 0.08])
            lc1.write(m["name"])
            lc2.caption(T("{k} kcal · P {p} · C {c} · G {g}").format(
                k=fmt_num(m["kcal"]), p=fmt_num(m["protein"]),
                c=fmt_num(m["carbs"]), g=fmt_num(m["fat"])))
            if lc3.button("🗑️", key=f"del_meal_{m['id']}", help=T("Eliminar comida")):
                db.delete_meal(m["id"])
                st.rerun()

        # Estadísticas del día en una sola línea: diferencia · quemadas ·
        # consumidas · macros.
        tot = db.meals_totals(meal_date)
        mday = db.get_day(meal_date) or {}
        burned = mday.get("calories_burned")
        s = st.columns(6)
        if burned:
            diff = burned - tot["kcal"]
            s[0].metric(T("Diferencia"), f"{diff:+.0f} kcal",
                        delta=T("déficit") if diff >= 0 else T("superávit"),
                        delta_color="off",
                        help=T("Quemadas − consumidas. Positivo = déficit (gastas más de lo que comes)."))
            s[1].metric(T("Quemadas"), f"{burned:.0f} kcal",
                        help=T("De Whoop (gasto total del día)."))
        else:
            s[0].metric(T("Diferencia"), "—",
                        help=T("Necesita el dato de calorías quemadas de Whoop."))
            s[1].metric(T("Quemadas"), "—", help=T("De Whoop (gasto total del día)."))
        s[2].metric(T("Consumidas"), f"{fmt_num(tot['kcal'])} kcal")
        s[3].metric(T("Proteínas"), f"{fmt_num(tot['protein'])} g")
        s[4].metric(T("Carbohidratos"), f"{fmt_num(tot['carbs'])} g")
        s[5].metric(T("Grasas"), f"{fmt_num(tot['fat'])} g")
        if not burned:
            st.caption(T("Sin dato de calorías quemadas de Whoop para este día. "
                         "Sincroniza Whoop (o reimporta los CSV) para ver el balance."))

    # Días pasados: tabla con quemadas, consumidas y la diferencia.
    with cal_hist:
        if not _meals_by_day:
            st.caption(T("Aún no has registrado comidas. Empieza en la pestaña «Registrar»."))
        else:
            rows = []
            for d in sorted(_meals_by_day, reverse=True):
                consumed = round(_meals_by_day[d]["kcal"] or 0)
                dd = db.get_day(d) or {}
                bd = dd.get("calories_burned")
                bd = round(bd) if bd else None
                rows.append({
                    T("Día"): d,
                    T("Quemadas (Whoop)"): bd,
                    T("Consumidas"): consumed,
                    T("Diferencia"): (bd - consumed) if bd is not None else None,
                })
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption(T("Diferencia = quemadas − consumidas. Positivo = déficit calórico."))

            # Evolución: quemadas vs consumidas (solo días con ambos datos). El área
            # entre las líneas se pinta verde si quemas más y rojo si comes más; los
            # días sin datos se saltan y los huecos se marcan con una vertical.
            ev = sorted(cal_rows)[-30:]   # últimos 30 días CON datos (ignora los faltantes)
            if len(ev) >= 2:
                dates = [d for d, _, _ in ev]
                xs = list(range(len(ev)))
                burned_y = [b for _, b, _ in ev]
                consumed_y = [c for _, _, c in ev]
                # Para que el relleno NO se salga en los cruces, insertamos el punto
                # exacto de cruce (x fraccionario, donde ambas líneas valen lo mismo)
                # en las series que definen el área. Así, en cada tramo una línea
                # está siempre por encima y el max/min coincide con las líneas.
                ax, ab, ac = [], [], []
                for i in range(len(xs)):
                    ax.append(xs[i]); ab.append(burned_y[i]); ac.append(consumed_y[i])
                    if i < len(xs) - 1:
                        d0 = burned_y[i] - consumed_y[i]
                        d1 = burned_y[i + 1] - consumed_y[i + 1]
                        if d0 * d1 < 0:                      # se cruzan dentro del tramo
                            t = d0 / (d0 - d1)
                            yc = burned_y[i] + t * (burned_y[i + 1] - burned_y[i])
                            ax.append(xs[i] + t); ab.append(yc); ac.append(yc)
                up = [max(b, c) for b, c in zip(ab, ac)]    # techo (verde)
                lo = [min(b, c) for b, c in zip(ab, ac)]    # suelo (rojo)
                ev_fig = go.Figure()
                # Verde entre consumidas y max(.): solo donde quemadas > consumidas.
                ev_fig.add_trace(go.Scatter(x=ax, y=ac, mode="lines",
                                            line=dict(width=0), hoverinfo="skip",
                                            showlegend=False))
                ev_fig.add_trace(go.Scatter(x=ax, y=up, mode="lines", line=dict(width=0),
                                            fill="tonexty", fillcolor="rgba(46,204,113,0.35)",
                                            hoverinfo="skip", showlegend=False))
                # Rojo entre min(.) y consumidas: solo donde consumidas > quemadas.
                ev_fig.add_trace(go.Scatter(x=ax, y=lo, mode="lines", line=dict(width=0),
                                            hoverinfo="skip", showlegend=False))
                ev_fig.add_trace(go.Scatter(x=ax, y=ac, mode="lines",
                                            line=dict(width=0), fill="tonexty",
                                            fillcolor="rgba(231,76,60,0.35)",
                                            hoverinfo="skip", showlegend=False))
                # Líneas visibles encima.
                _txt = [d.isoformat() for d in dates]
                ev_fig.add_trace(go.Scatter(
                    x=xs, y=burned_y, mode="lines+markers", name=T("Quemadas"),
                    line=dict(color="#6c5ce7", width=2.5), text=_txt,   # índigo: resalta sobre el verde
                    hovertemplate="%{text}<br>" + T("Quemadas") + "=%{y:.0f} kcal<extra></extra>"))
                ev_fig.add_trace(go.Scatter(
                    x=xs, y=consumed_y, mode="lines+markers", name=T("Consumidas"),
                    line=dict(color=AMBER, width=2.5), text=_txt,
                    hovertemplate="%{text}<br>" + T("Consumidas") + "=%{y:.0f} kcal<extra></extra>"))
                # Huecos: vertical punteada entre días no consecutivos.
                for i in range(len(dates) - 1):
                    if (dates[i + 1] - dates[i]).days > 1:
                        ev_fig.add_vline(x=i + 0.5, line=dict(
                            color="rgba(150,150,150,0.6)", width=1, dash="dot"))
                # Línea horizontal: punto medio entre las medias globales de quemadas
                # y consumidas (sobre TODO el histórico con ambos datos, sin contar hoy).
                if cal_rows_avg:
                    _gb = sum(b for _, b, _ in cal_rows_avg) / len(cal_rows_avg)
                    _gc = sum(c for _, _, c in cal_rows_avg) / len(cal_rows_avg)
                    _mid = (_gb + _gc) / 2
                    ev_fig.add_hline(
                        y=_mid, line=dict(color="rgba(150,150,150,0.9)", width=1.5, dash="dash"),
                        annotation_text=f"{T('Media global')} {_mid:.0f} kcal",
                        annotation_position="top left",
                        annotation_font=dict(color=_fg(), size=11))
                ev_fig.update_layout(
                    height=360, margin=dict(l=10, r=10, t=80, b=60),
                    title={"text": T("Evolución: quemadas vs consumidas"), "x": 0.5,
                           "xanchor": "center", "y": 0.97, "yanchor": "top"},
                    yaxis_title="kcal", paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)", font=dict(color=_fg()),
                    legend=dict(orientation="h", y=1.04, x=0.5, xanchor="center",
                                yanchor="bottom"))
                ev_fig.update_xaxes(tickmode="array", tickvals=xs,
                                    ticktext=[d.strftime("%d/%m") for d in dates],
                                    tickangle=-45, tickfont=dict(size=10))
                ev_fig.update_yaxes(automargin=True)
                st.plotly_chart(ev_fig, width="stretch", theme=None)
                st.caption(T("🟢 área verde = quemas más (déficit) · 🔴 roja = comes más. "
                             "Las verticales punteadas marcan huecos de días sin datos. "
                             "La línea gris discontinua es el punto medio entre las medias "
                             "globales de quemadas y consumidas."))

    # Comidas guardadas: la "base de datos" de comidas recurrentes.
    with cal_db:
        st.caption(T("Comidas que repites a menudo. Guárdalas aquí y añádelas con un clic "
                     "desde la pestaña «Registrar»."))
        with st.form("add_preset", clear_on_submit=True):
            dc = st.columns([0.4, 0.15, 0.15, 0.15, 0.15])
            d_name = dc[0].text_input(T("Comida"), placeholder=T("p. ej. Tortilla francesa"))
            d_kcal = dc[1].number_input("kcal", 0.0, 10000.0, step=50.0,
                                        format="%.1f", key="preset_kcal")
            d_prot = dc[2].number_input(T("Prot (g)"), 0.0, 1000.0, step=5.0,
                                        format="%.1f", key="preset_prot")
            d_carb = dc[3].number_input("Carbs (g)", 0.0, 1000.0, step=5.0,
                                        format="%.1f", key="preset_carb")
            d_fat = dc[4].number_input(T("Grasa (g)"), 0.0, 1000.0, step=5.0,
                                       format="%.1f", key="preset_fat")
            if st.form_submit_button(T("💾 Guardar comida"), width="stretch") and d_name.strip():
                db.add_meal_preset(d_name.strip(), d_kcal, d_prot, d_carb, d_fat)
                st.rerun()

        pres = db.get_meal_presets()
        if not pres:
            st.caption(T("Todavía no hay comidas guardadas."))
        for p in pres:
            gc1, gc2, gc3 = st.columns([0.5, 0.42, 0.08])
            gc1.write(f"**{p['name']}**")
            gc2.caption(T("{k} kcal · P {p} · C {c} · G {g}").format(
                k=fmt_num(p["kcal"]), p=fmt_num(p["protein"]),
                c=fmt_num(p["carbs"]), g=fmt_num(p["fat"])))
            if gc3.button("🗑️", key=f"del_preset_{p['id']}", help=T("Eliminar comida guardada")):
                db.delete_meal_preset(p["id"])
                st.rerun()

with cal_cal:
    # Espacio arriba para que el calendario baje y quede a la altura del contenido
    # de las pestañas (no pegado a la barra de pestañas).
    st.markdown("<div style='height:5rem'></div>", unsafe_allow_html=True)
    # Mes mostrado = actual + offset (≤ 0; no se permite ir al futuro).
    _coff = st.session_state.get("cal_offset", 0)
    _cbase = date.today().replace(day=1)
    _cy = _cbase.year + (_cbase.month - 1 + _coff) // 12
    _cm = (_cbase.month - 1 + _coff) % 12 + 1

    cnav = st.columns([0.16, 0.68, 0.16])
    if cnav[0].button("◀", key="cal_prev", help=T("Mes anterior"), width="stretch"):
        st.session_state.cal_offset = _coff - 1
        st.rerun()
    cnav[1].markdown(
        f"<div style='text-align:center;font-weight:600;'>⚖️ Balance · "
        f"{_MONTHS[_cm - 1]} {_cy}</div>", unsafe_allow_html=True)
    if cnav[2].button("▶", key="cal_next", help=T("Mes siguiente"),
                      width="stretch", disabled=_coff >= 0):
        st.session_state.cal_offset = _coff + 1
        st.rerun()

    st.markdown(calorie_calendar_html(_cy, _cm, cal_diffs, date.today()),
                unsafe_allow_html=True)
    st.caption(T("🟢 déficit > 200 · 🟡 entre −200 y 200 · 🔴 superávit > 200 kcal. "
                 "Solo se colorean los días con comidas y dato de Whoop. "
                 "Pincha un día para editar sus comidas."))

    # Medias: último mes y global (solo días con comidas y dato de Whoop, sin hoy).
    _recent = [(b, c) for (do, b, c) in cal_rows_avg
               if do >= date.today() - timedelta(days=30)]
    render_avg_block(T("Media · últimos 30 días"), _recent)
    render_avg_block(T("Media · global"), [(b, c) for (_, b, c) in cal_rows_avg])


# --- Actividad de hoy (workouts importados de Whoop) ---
st.markdown(f"### {T('Actividad de hoy')}")
workouts_today = db.get_workouts(TODAY)
zones = [day.get(f"hr_zone{i}_min") or 0 for i in range(1, 6)]
# Zona 0 = tiempo por debajo de Z1 = total − suma(Z1..Z5).
zone_vals = [max(0.0, (day.get("workout_min") or 0) - sum(zones))] + zones
if workouts_today or day.get("workout_min"):
    a1, a2, a3 = st.columns(3)
    a1.metric(T("Tiempo total"), f"{int(day.get('workout_min') or 0)} min")
    a2.metric(T("Calorías"), f"{int(day.get('workout_calories') or 0)} cal")
    a3.metric(T("FC media"), f"{int(day.get('workout_avg_hr') or 0)} ppm")
    if sum(zone_vals) > 0:
        zfig = go.Figure(go.Bar(
            x=[f"<b>Z{i}</b>" for i in range(6)], y=zone_vals,
            marker_color=["#95a5a6", GREEN, STRAIN_COLOR, AMBER, "#e67e22", RED],
            text=[f"<b>{z:.0f}</b>" if z > 0 else "" for z in zone_vals],
            textposition="inside", insidetextanchor="middle",
            insidetextfont=dict(size=20),   # color automático: contrasta con cada barra
        ))
        zfig.update_layout(
            height=270, margin=dict(l=15, r=10, t=48, b=45),
            title={"text": T("Minutos por zona de FC"), "x": 0.5, "xanchor": "center",
                   "font": {"size": 18}},
            yaxis_title="min", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font=dict(color=_fg(), size=13),
        )
        zfig.update_xaxes(automargin=True, tickfont=dict(size=15))
        zfig.update_yaxes(automargin=True)
        st.plotly_chart(zfig, width="stretch", theme=None)
    for w in workouts_today:
        st.write(
            f"🏃 **{w['activity'] or T('Actividad')}** · {w['start']} · "
            f"{(w['duration_min'] or 0):.0f} min · {(w['calories'] or 0):.0f} cal · "
            f"{T('FC media')} {(w['avg_hr'] or 0):.0f} / {T('máx')} {(w['max_hr'] or 0):.0f} ppm"
        )
else:
    st.caption(T("No hay actividades registradas hoy. Importa tu export de Whoop "
                 "desde la barra lateral."))


# ---------------------------------------------------------------------------
# ANÁLISIS
# ---------------------------------------------------------------------------
st.divider()
st.header(T("Análisis"))

all_vars = db.INPUT_VARS + db.WHOOP_VARS

# X/Y pickers: agrupa las variables booleanas (0/1) separadas del resto con una
# cabecera, y marca con ⭐ unas cuantas clave para localizarlas rápido en la lista.
# (Streamlit no permite colorear el texto de un selectbox, así que el ⭐ hace de
# "color que destaca" y se ve dentro del desplegable.)
HIGHLIGHT_VARS = {"entreno_manana", "pantalla_noche_min", "recovery", "strain",
                  "hrv", "rhr", "hora_dormir_num"}
_SEP_LABELS = {"__hdr_bool__": "──────── booleanas (0/1) ────────",
               "__hdr_num__": "──────── numéricas ────────"}
_bool_vars = [v for v in all_vars if v in db.BOOL_HABITS]
_other_vars = [v for v in all_vars if v not in db.BOOL_HABITS]
VAR_OPTIONS = ["__hdr_bool__"] + _bool_vars + ["__hdr_num__"] + _other_vars


def var_label(v):
    if v in _SEP_LABELS:
        return T(_SEP_LABELS[v])
    name = label(v)
    return f"⭐ {name}" if v in HIGHLIGHT_VARS else name


lag = st.toggle(
    T("Lag +1 día  ·  hábito de hoy → biometría de mañana"),
    value=True,
    help=T("Recovery, HRV, RHR y sueño se miden por la mañana y reflejan la noche "
           "anterior, así que con el lag se emparejan hábito[día] con whoop[día+1]. "
           "El Strain se acumula durante el día, así que SIEMPRE es del mismo día (no "
           "se desplaza con el lag). Los datos manuales (incl. Pantalla noche y Pasos) "
           "se registran en su día real, así que tampoco se desplazan."),
)

cx, cy = st.columns(2)
xvar = cx.selectbox("Variable X", VAR_OPTIONS,
                    index=VAR_OPTIONS.index("hora_dormir_num"), format_func=var_label)
yvar = cy.selectbox("Variable Y", VAR_OPTIONS,
                    index=VAR_OPTIONS.index("recovery"), format_func=var_label)
# Las cabeceras son solo separadores: si se eligen, vuelve al valor por defecto.
if xvar in _SEP_LABELS:
    xvar = "hora_dormir_num"
if yvar in _SEP_LABELS:
    yvar = "recovery"

aligned = analysis.build_aligned(df, lag)
r, n = analysis.pearson(aligned, xvar, yvar)

k1, k2, k3 = st.columns(3)
k1.metric("Pearson r", f"{r:+.2f}" if r is not None else "—")
k2.metric(T("Fuerza"), T(analysis.strength_label(r)))
k3.metric(T("n (días emparejados)"), n)

if n < 30:
    st.warning(T("⚠️ Solo {n} días emparejados. Con n < 30 los resultados pueden ser "
                 "ruido — no saques conclusiones todavía.").format(n=n))

if xvar in aligned and yvar in aligned:
    sub = aligned[["date", xvar, yvar]].copy()
    sub[xvar] = pd.to_numeric(sub[xvar], errors="coerce")
    sub[yvar] = pd.to_numeric(sub[yvar], errors="coerce")
    sub = sub.dropna(subset=[xvar, yvar]).sort_values("date")
else:
    sub = pd.DataFrame()

if len(sub) >= 1 and xvar != yvar:
    # Colour points by recency: oldest = rojo, más reciente = azul.
    recency = (sub["date"] - sub["date"].min()).dt.days
    sc = go.Figure()
    sc.add_trace(go.Scatter(
        x=sub[xvar], y=sub[yvar], mode="markers",
        marker=dict(size=9, opacity=0.85, color=recency,
                    colorscale=[[0, RED], [1, "#2e86de"]],
                    colorbar=dict(title=T("reciente →")), showscale=True),
        text=sub["date"].dt.strftime("%Y-%m-%d"),
        hovertemplate=f"%{{text}}<br>{label(xvar)}=%{{x}}<br>{label(yvar)}=%{{y}}<extra></extra>",
    ))
    if len(sub) >= 3 and sub[xvar].nunique() > 1:
        coef = np.polyfit(sub[xvar], sub[yvar], 1)
        xs = np.array([sub[xvar].min(), sub[xvar].max()])
        sc.add_trace(go.Scatter(x=xs, y=coef[0] * xs + coef[1], mode="lines",
                                name="ajuste", line=dict(color="#888888", dash="dash")))
    sc.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                     showlegend=False, xaxis_title=label(xvar), yaxis_title=label(yvar))
    st.plotly_chart(sc, width="stretch")
else:
    st.info(T("Elige dos variables distintas con datos suficientes para ver el scatter."))

# --- correlation matrix ----------------------------------------------------
st.subheader(T("Matriz de correlaciones (exploratoria)"))
st.caption(T("Hábitos y actividad (filas) × métricas Whoop (columnas). Es **exploratoria**: "
             "son muchas pruebas simultáneas, así que algunas celdas parecerán fuertes por "
             "puro azar. No implica causalidad. (Rojo = negativa, azul = positiva.)"))

# Variables secundarias: se ocultan por defecto para no saturar la matriz, y se
# muestran solo si activas el toggle. Cubre filas (Siesta) y columnas (sueño/Whoop).
HIDDEN_MATRIX_VARS = {"siesta", "sleep_hours", "sleep_performance",
                      "resp_rate", "skin_temp", "spo2"}
show_all_matrix = st.toggle(
    T("Mostrar todas las variables"), value=False,
    help=T("Por defecto se ocultan Siesta, Horas de sueño, Rendimiento sueño, "
           "Frec. respiratoria, Temp. piel y SpO₂ para que la matriz sea más legible. "
           "Actívalo para verlas todas."),
)

r_mat, n_mat = analysis.corr_matrix(df, lag)
if not show_all_matrix:
    keep_rows = [i for i in r_mat.index if i not in HIDDEN_MATRIX_VARS]
    keep_cols = [c for c in r_mat.columns if c not in HIDDEN_MATRIX_VARS]
    r_mat = r_mat.loc[keep_rows, keep_cols]
    n_mat = n_mat.loc[keep_rows, keep_cols]
# Oculta variables con pocos datos: si en TODA su fila/columna no se alcanzan 30
# días emparejados, sus correlaciones serían puro ruido, así que no se muestran.
keep_rows = [i for i in r_mat.index if n_mat.loc[i].max() >= 30]
keep_cols = [c for c in r_mat.columns if n_mat[c].max() >= 30]
r_mat = r_mat.loc[keep_rows, keep_cols]
n_mat = n_mat.loc[keep_rows, keep_cols]

if r_mat.empty:
    st.info(T("No hay variables con suficientes datos (≥30 días emparejados) para la matriz."))
else:
    z = r_mat.values.astype(float)

    # Theme-aware palette so the matrix blends in light AND dark mode: in dark mode
    # r≈0 maps to a dark tone instead of RdBu's white (which would clash).
    colorscale = ([[0.0, "#c0392b"], [0.5, "#23232b"], [1.0, "#2e86de"]]
                  if _is_dark() else "RdBu")
    fg = _fg()

    heat = go.Figure(go.Heatmap(
        z=z,
        x=[label(c) for c in r_mat.columns],
        y=[label(i) for i in r_mat.index],
        zmin=-1, zmax=1, colorscale=colorscale,
        text=[[("" if np.isnan(v) else f"{v:.2f}") for v in row] for row in z],
        texttemplate="%{text}",
        textfont=dict(color=fg),
        customdata=n_mat.values.astype(int),
        hovertemplate="r=%{z:.2f}<br>n=%{customdata} " + T("días") + "<extra></extra>",
        colorbar=dict(title="r"),
    ))
    heat.update_layout(
        height=430, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=fg),
    )
    # automargin so the long row/column labels get room (theme=None disables the
    # automatic margins Streamlit's theme used to add), tickfont so they stay visible.
    heat.update_xaxes(side="top", automargin=True, tickfont=dict(color=fg))
    heat.update_yaxes(automargin=True, tickfont=dict(color=fg))
    st.plotly_chart(heat, width="stretch", theme=None)

    st.caption(T("Pista: prueba X = «Hora de dormir», Y = «Recovery». Con el lag activado "
                 "debería aparecer una relación; al desactivarlo, desaparece."))
