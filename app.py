"""Señal — personal habit ↔ biometrics correlation tracker (Phase 1).

Run with:  streamlit run app.py
"""
import calendar
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis
import db
import whoop_import

st.set_page_config(page_title="Señal", page_icon="📡", layout="wide")

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


def label(v):
    return db.LABELS.get(v, v)


def default(d, key, fallback):
    """Stored value for `key`, or `fallback` when it's missing/NULL.
    (Avoids the `x or fallback` trap where a real 0 would be replaced.)"""
    val = d.get(key)
    return fallback if val is None else val


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
_WEEKDAYS_ES = ["L", "M", "X", "J", "V", "S", "D"]
_NOFAP_CROSS = "#2ecc71"   # color de la ✗ de NoFap (verde = día logrado)


def nofap_calendar_html(year, month, nofap_dates, today):
    """Mini-calendario HTML del mes: marca con ✗ los días de NoFap (fap == 0).

    Usa table-layout:fixed + ancho 1/7 por columna para que las 7 columnas sean
    idénticas en todos los meses (en modo auto se ajustarían al contenido).
    """
    fg = _fg()
    head = "".join(
        f"<th style='width:14.28%;padding:3px;font-size:11px;color:{fg};"
        f"opacity:.55;'>{d}</th>" for d in _WEEKDAYS_ES)
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


# ---------------------------------------------------------------------------
# Sidebar — data management
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Datos")
    st.metric("Días registrados", db.count_days())
    if st.button("🗑️ Borrar todo", width="stretch"):
        db.clear_all()
        st.rerun()

    st.divider()
    st.subheader("Importar Whoop")
    st.caption("Sube tu export de Whoop (uno o varios CSV). Sustituye los datos "
               "actuales por los reales.")
    up_phys = st.file_uploader("physiological_cycles.csv", type="csv", key="up_phys")
    up_work = st.file_uploader("workouts.csv", type="csv", key="up_work")
    up_jour = st.file_uploader("journal_entries.csv", type="csv", key="up_jour")
    up_sleep = st.file_uploader("sleeps.csv", type="csv", key="up_sleep")
    if st.button("⬆️ Importar CSV subidos", width="stretch"):
        if not any([up_phys, up_work, up_jour, up_sleep]):
            st.warning("Sube al menos un CSV primero.")
        else:
            s = whoop_import.import_whoop(up_phys, up_jour, up_work, up_sleep)
            st.success(f"Importado: {s['days']} días, {s['workouts']} actividades.")
            st.rerun()
    if st.button("📂 Importar desde /data", width="stretch",
                 help="Lee los CSV de Whoop guardados en la carpeta ./data"):
        s = whoop_import.import_from_folder(DATA_DIR)
        if not s:
            st.warning("No encontré CSV de Whoop en ./data.")
        else:
            st.success(f"Importado: {s['days']} días, {s['workouts']} actividades.")
            st.rerun()
    st.caption("💾 Los datos se guardan en `senal.db` y persisten entre cambios. "
               "Si dejas tus CSV en `./data`, se recargan solos cuando haga falta. "
               "Al reimportar se conservan tus datos manuales (Japonés, Pantalla "
               "noche, tareas).")


# ---------------------------------------------------------------------------
# HOY
# ---------------------------------------------------------------------------
st.title("📡 Señal")
st.caption("Registra tus hábitos y biometría, y explora qué mueve de verdad tu recovery.")

st.header("Hoy")
st.subheader(TODAY)

day = db.get_day(TODAY) or {}
# Todos los días, cargados una sola vez (para el calendario NoFap y el análisis).
df = db.load_days_df()

# --- Whoop rings (read-only; filled by the Whoop CSV import) ---
g = st.columns(5)
g[0].plotly_chart(ring(day.get("recovery"), "Recovery", 0, 100,
                       _band_color(day.get("recovery"), 67, 34)), width="stretch")
g[1].plotly_chart(ring(day.get("hrv"), "HRV (ms)", 20, 60,
                       _band_color(day.get("hrv"), 47, 33)), width="stretch")
g[2].plotly_chart(ring(day.get("strain"), "Strain", 0, 21, STRAIN_COLOR,
                       decimals=1), width="stretch")
g[3].plotly_chart(ring(day.get("rhr"), "RHR (ppm)", 100, 50,
                       _band_color(day.get("rhr"), 65, 75, higher_better=False)), width="stretch")
g[4].plotly_chart(ring(day.get("sleep_hours"), "Sueño (h)", 0, 9,
                       _band_color(day.get("sleep_hours"), 7.5, 6.5), decimals=1), width="stretch")

# --- habit logger (izq.) + calendario NoFap (dcha.) ---
log_col, cal_col = st.columns([0.62, 0.38])
with log_col:
    with st.form("logger"):
        st.markdown("**Hábitos**")
        h = st.columns(3)
        entreno = h[0].checkbox("Entreno mañana", bool(day.get("entreno_manana")))
        estir = h[1].checkbox("Estiramientos", bool(day.get("estiramientos")))
        journ = h[2].checkbox("Journaling", bool(day.get("journaling")))
        h2 = st.columns(3)
        leer = h2[0].checkbox("Leer en cama", bool(day.get("leer")))
        fap = h2[1].checkbox("Fap", bool(day.get("fap")))
        agua = h2[2].checkbox("Beber agua (min 3 botellas)", bool(day.get("beber_agua")))

        n1, n2 = st.columns(2)
        japones = n1.slider("Japonés (min)", 0, 120,
                            min(int(default(day, "japones_min", 0)), 120))
        pantalla = n2.slider("Pantalla noche (min)", 0, 120,
                             min(int(default(day, "pantalla_noche_min", 0)), 120),
                             help="Minutos de pantalla de anoche. Como lo registras a "
                                  "la mañana siguiente, en el análisis se desplaza como "
                                  "una métrica de la noche anterior.")

        saved = st.form_submit_button("💾 Guardar hoy", width="stretch")

with cal_col:
    _nofap = set()
    if not df.empty and "fap" in df.columns:
        _nofap = set(pd.to_datetime(df.loc[df["fap"] == 0, "date"]).dt.date)

    # Mes mostrado = mes actual + offset (≤ 0; no se permite ir al futuro).
    _off = st.session_state.get("nofap_offset", 0)
    _base = date.today().replace(day=1)
    _y = _base.year + (_base.month - 1 + _off) // 12
    _m = (_base.month - 1 + _off) % 12 + 1

    nav = st.columns([0.16, 0.68, 0.16])
    if nav[0].button("◀", key="nofap_prev", help="Mes anterior", width="stretch"):
        st.session_state.nofap_offset = _off - 1
        st.rerun()
    nav[1].markdown(
        f"<div style='text-align:center;font-weight:600;'>🚫 NoFap · "
        f"{_MONTHS_ES[_m - 1]} {_y}</div>", unsafe_allow_html=True)
    if nav[2].button("▶", key="nofap_next", help="Mes siguiente",
                     width="stretch", disabled=_off >= 0):
        st.session_state.nofap_offset = _off + 1
        st.rerun()

    st.markdown(nofap_calendar_html(_y, _m, _nofap, date.today()),
                unsafe_allow_html=True)
    _n_month = sum(1 for x in _nofap if x.year == _y and x.month == _m)
    st.caption(f"Días tachados = NoFap. En {_MONTHS_ES[_m - 1]}: {_n_month}.")

if saved:
    db.upsert_day(TODAY, {
        "entreno_manana": int(entreno),
        "estiramientos": int(estir),
        "journaling": int(journ),
        "leer": int(leer),
        "fap": int(fap),
        "beber_agua": int(agua),
        "japones_min": int(japones),
        "pantalla_noche_min": int(pantalla),
        "tareas_pct": db.tasks_pct(TODAY),
    })
    st.success("Día guardado ✅")

# --- tasks (hoy a la izq. · mañana a la dcha.) -----------------------------
hoy_col, manana_col = st.columns(2)

with hoy_col:
    st.markdown("### Tareas de hoy")
    for t in db.get_tasks(TODAY):
        tc1, tc2 = st.columns([0.92, 0.08])
        checked = tc1.checkbox(t["text"], bool(t["done"]), key=f"task_{t['id']}")
        if checked != bool(t["done"]):
            db.set_task_done(t["id"], checked)
            db.upsert_day(TODAY, {"tareas_pct": db.tasks_pct(TODAY)})
            st.rerun()
        if tc2.button("🗑️", key=f"del_{t['id']}", help="Eliminar tarea"):
            db.delete_task(t["id"])
            db.upsert_day(TODAY, {"tareas_pct": db.tasks_pct(TODAY)})
            st.rerun()

    with st.form("add_task", clear_on_submit=True):
        ac1, ac2 = st.columns([0.85, 0.15])
        new_task = ac1.text_input("Nueva tarea", label_visibility="collapsed",
                                  placeholder="Añadir tarea…")
        if ac2.form_submit_button("➕ Añadir", width="stretch") and new_task.strip():
            db.add_task(TODAY, new_task.strip())
            db.upsert_day(TODAY, {"tareas_pct": db.tasks_pct(TODAY)})
            st.rerun()

    pct_today = db.tasks_pct(TODAY)
    st.progress((pct_today or 0) / 100,
                text=f"Tareas completadas: {0 if pct_today is None else pct_today:.0f}%")

with manana_col:
    st.markdown("### Tareas para mañana")
    st.caption(f"Se planifican para el {TOMORROW}. Mañana aparecerán en «Tareas de hoy».")
    for t in db.get_tasks(TOMORROW):
        mc1, mc2 = st.columns([0.92, 0.08])
        mc1.write(f"• {t['text']}")
        if mc2.button("🗑️", key=f"del_tmrw_{t['id']}", help="Eliminar tarea"):
            db.delete_task(t["id"])
            st.rerun()

    with st.form("add_task_tmrw", clear_on_submit=True):
        bc1, bc2 = st.columns([0.85, 0.15])
        new_task_t = bc1.text_input("Nueva tarea mañana", label_visibility="collapsed",
                                    placeholder="Añadir tarea para mañana…")
        if bc2.form_submit_button("➕ Añadir", width="stretch") and new_task_t.strip():
            db.add_task(TOMORROW, new_task_t.strip())
            st.rerun()

# --- Actividad de hoy (workouts importados de Whoop) ---
st.markdown("### Actividad de hoy")
workouts_today = db.get_workouts(TODAY)
zones = [day.get(f"hr_zone{i}_min") or 0 for i in range(1, 6)]
if workouts_today or day.get("workout_min"):
    a1, a2, a3 = st.columns(3)
    a1.metric("Tiempo total", f"{int(day.get('workout_min') or 0)} min")
    a2.metric("Calorías", f"{int(day.get('workout_calories') or 0)} cal")
    a3.metric("FC media", f"{int(day.get('workout_avg_hr') or 0)} ppm")
    if sum(zones) > 0:
        zfig = go.Figure(go.Bar(
            x=[f"Z{i}" for i in range(1, 6)], y=zones,
            marker_color=[GREEN, STRAIN_COLOR, AMBER, "#e67e22", RED],
            text=[f"{z:.0f}" for z in zones], textposition="outside",
        ))
        zfig.update_layout(
            height=240, margin=dict(l=10, r=10, t=40, b=10),
            title={"text": "Minutos por zona de FC", "x": 0.5, "xanchor": "center"},
            yaxis_title="min", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font=dict(color=_fg()),
        )
        st.plotly_chart(zfig, width="stretch", theme=None)
    for w in workouts_today:
        st.write(
            f"🏃 **{w['activity'] or 'Actividad'}** · {w['start']} · "
            f"{(w['duration_min'] or 0):.0f} min · {(w['calories'] or 0):.0f} cal · "
            f"FC media {(w['avg_hr'] or 0):.0f} / máx {(w['max_hr'] or 0):.0f} ppm"
        )
else:
    st.caption("No hay actividades registradas hoy. Importa tu export de Whoop "
               "desde la barra lateral.")


# ---------------------------------------------------------------------------
# ANÁLISIS
# ---------------------------------------------------------------------------
st.divider()
st.header("Análisis")

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
        return _SEP_LABELS[v]
    name = label(v)
    return f"⭐ {name}" if v in HIGHLIGHT_VARS else name


lag = st.toggle(
    "Lag +1 día  ·  hábito de hoy → biometría de mañana",
    value=True,
    help="Recovery, HRV, RHR y sueño se miden por la mañana y reflejan la noche "
         "anterior, así que con el lag se emparejan hábito[día] con whoop[día+1]. "
         "Pantalla noche se registra a la mañana siguiente, así que también se "
         "desplaza. El Strain se acumula durante el día, así que SIEMPRE es del "
         "mismo día (no se desplaza con el lag).",
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
k2.metric("Fuerza", analysis.strength_label(r))
k3.metric("n (días emparejados)", n)

if n < 30:
    st.warning(f"⚠️ Solo {n} días emparejados. Con n < 30 los resultados pueden ser "
               "ruido — no saques conclusiones todavía.")

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
                    colorbar=dict(title="reciente →"), showscale=True),
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
    st.info("Elige dos variables distintas con datos suficientes para ver el scatter.")

# --- correlation matrix ----------------------------------------------------
st.subheader("Matriz de correlaciones (exploratoria)")
st.caption("Hábitos y actividad (filas) × métricas Whoop (columnas). Es **exploratoria**: "
           "son muchas pruebas simultáneas, así que algunas celdas parecerán fuertes por "
           "puro azar. No implica causalidad. (Rojo = negativa, azul = positiva.)")

# Variables secundarias: se ocultan por defecto para no saturar la matriz, y se
# muestran solo si activas el toggle. Cubre filas (Siesta) y columnas (sueño/Whoop).
HIDDEN_MATRIX_VARS = {"siesta", "sleep_hours", "sleep_performance",
                      "resp_rate", "skin_temp", "spo2"}
show_all_matrix = st.toggle(
    "Mostrar todas las variables", value=False,
    help="Por defecto se ocultan Siesta, Horas de sueño, Rendimiento sueño, "
         "Frec. respiratoria, Temp. piel y SpO₂ para que la matriz sea más legible. "
         "Actívalo para verlas todas.",
)

r_mat, n_mat = analysis.corr_matrix(df, lag)
if not show_all_matrix:
    keep_rows = [i for i in r_mat.index if i not in HIDDEN_MATRIX_VARS]
    keep_cols = [c for c in r_mat.columns if c not in HIDDEN_MATRIX_VARS]
    r_mat = r_mat.loc[keep_rows, keep_cols]
    n_mat = n_mat.loc[keep_rows, keep_cols]
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
    hovertemplate="r=%{z:.2f}<br>n=%{customdata} días<extra></extra>",
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

st.caption("Pista: prueba X = «Hora de dormir», Y = «Recovery». Con el lag activado "
           "debería aparecer una relación; al desactivarlo, desaparece.")
