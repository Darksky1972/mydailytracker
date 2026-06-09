"""SQLite storage layer for Señal.

One row per calendar day in `days`, plus `tasks`, `workouts`, and a tiny `meta`
key/value table. The schema is defined once in DAYS_SCHEMA and a small migration
adds any missing columns to an existing database (so upgrades are painless).
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "senal.db"

# --- variable groups -------------------------------------------------------
BOOL_HABITS = ["entreno_manana", "estiramientos", "journaling", "leer", "fap",
               "beber_agua", "cafeina", "alcohol", "comer_restaurante", "siesta"]
NUM_HABITS = ["japones_min", "pantalla_noche_min", "pasos"]
# Numeric habit variables exposed in the análisis section:
HABIT_VARS = BOOL_HABITS + NUM_HABITS + ["hora_dormir_num", "tareas_pct"]
# Activity/workout variables — also INPUTS (things you do), not shifted by lag:
WORKOUT_VARS = ["workout_min", "workout_calories", "workout_avg_hr"]
# Everything on the "input" side of a correlation (matrix rows / X axis):
INPUT_VARS = HABIT_VARS + WORKOUT_VARS
# Whoop biometrics — OUTPUTS (matrix columns / Y axis).
WHOOP_VARS = ["recovery", "strain", "hrv", "rhr", "sleep_hours",
              "sleep_performance", "resp_rate", "skin_temp", "spo2"]
# Strain accumulates DURING the day → same-day metric, never lagged. The rest are
# morning readings that reflect the previous night, so the lag toggle shifts them.
SAMEDAY_WHOOP = ["strain"]
LAGGED_WHOOP = [v for v in WHOOP_VARS if v not in SAMEDAY_WHOOP]
# Ya no hay inputs manuales con lag: Pantalla noche y Pasos se registran en su día
# real (con el selector Hoy/Ayer si se te pasó), así que no se desplazan.
LAGGED_INPUTS = []
# Everything that gets shifted when the lag toggle is on:
LAGGED_VARS = LAGGED_WHOOP + LAGGED_INPUTS

# Full `days` schema (name, SQL type). The PK is handled here too.
DAYS_SCHEMA = [
    ("date", "TEXT PRIMARY KEY"),
    # habits (bool 0/1)
    ("entreno_manana", "INTEGER"), ("estiramientos", "INTEGER"),
    ("journaling", "INTEGER"), ("leer", "INTEGER"), ("fap", "INTEGER"),
    ("beber_agua", "INTEGER"),
    ("cafeina", "INTEGER"), ("alcohol", "INTEGER"),
    ("comer_restaurante", "INTEGER"), ("siesta", "INTEGER"),
    # habits (numeric)
    ("japones_min", "INTEGER"), ("pantalla_noche_min", "INTEGER"),
    ("pasos", "INTEGER"),
    ("hora_dormir", "TEXT"), ("hora_dormir_num", "REAL"),
    ("tareas_pct", "REAL"),
    # whoop biometrics
    ("recovery", "REAL"), ("strain", "REAL"), ("hrv", "REAL"), ("rhr", "REAL"),
    ("sleep_hours", "REAL"), ("sleep_performance", "REAL"),
    ("resp_rate", "REAL"), ("skin_temp", "REAL"), ("spo2", "REAL"),
    # workout aggregates (per day)
    ("workout_min", "REAL"), ("workout_calories", "REAL"),
    ("workout_avg_hr", "REAL"), ("workout_max_hr", "REAL"),
    ("workout_count", "INTEGER"),
    ("hr_zone1_min", "REAL"), ("hr_zone2_min", "REAL"), ("hr_zone3_min", "REAL"),
    ("hr_zone4_min", "REAL"), ("hr_zone5_min", "REAL"),
    ("activities", "TEXT"),
]
# Every writable column of `days` (the `date` PK is handled separately).
DAY_COLUMNS = [name for name, _ in DAYS_SCHEMA if name != "date"]

WORKOUT_COLUMNS = ["date", "start", "activity", "duration_min", "calories",
                   "avg_hr", "max_hr", "strain",
                   "z1_min", "z2_min", "z3_min", "z4_min", "z5_min"]

# Human-readable labels for the UI.
LABELS = {
    "entreno_manana": "Entreno mañana",
    "estiramientos": "Estiramientos",
    "journaling": "Journaling",
    "leer": "Leer en cama",
    "fap": "Fap",
    "beber_agua": "Beber agua (min 3 botellas)",
    "cafeina": "Cafeína",
    "alcohol": "Alcohol",
    "comer_restaurante": "Comer en restaurante",
    "siesta": "Siesta",
    "japones_min": "Japonés (min)",
    "pantalla_noche_min": "Pantalla noche (min)",
    "pasos": "Pasos",
    "hora_dormir_num": "Hora de dormir",
    "tareas_pct": "Tareas completadas (%)",
    "workout_min": "Actividad (min)",
    "workout_calories": "Calorías actividad",
    "workout_avg_hr": "FC media actividad",
    "recovery": "Recovery",
    "strain": "Strain",
    "hrv": "HRV",
    "rhr": "RHR",
    "sleep_hours": "Horas de sueño",
    "sleep_performance": "Rendimiento sueño (%)",
    "resp_rate": "Frec. respiratoria",
    "skin_temp": "Temp. piel (°C)",
    "spo2": "SpO₂ (%)",
}


# --- connection ------------------------------------------------------------
@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    cols_sql = ", ".join(f"{name} {typ}" for name, typ in DAYS_SCHEMA)
    with _conn() as conn:
        conn.execute(f"CREATE TABLE IF NOT EXISTS days ({cols_sql})")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                date     TEXT NOT NULL,
                text     TEXT NOT NULL,
                done     INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 2
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                date         TEXT NOT NULL,
                start        TEXT,
                activity     TEXT,
                duration_min REAL,
                calories     REAL,
                avg_hr       REAL,
                max_hr       REAL,
                strain       REAL,
                z1_min REAL, z2_min REAL, z3_min REAL, z4_min REAL, z5_min REAL
            )
        """)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        # migrate: add any columns missing from an older `days` table
        existing = {row[1] for row in conn.execute("PRAGMA table_info(days)")}
        for name, typ in DAYS_SCHEMA:
            if name not in existing:
                conn.execute(
                    f"ALTER TABLE days ADD COLUMN {name} {typ.replace(' PRIMARY KEY', '')}")
        # migrate: older `tasks` tables may lack the priority column (1/2/3).
        task_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "priority" not in task_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 2")


# --- meta ------------------------------------------------------------------
def get_meta(key):
    with _conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(key, value):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


# --- bedtime helpers -------------------------------------------------------
def bedtime_to_num(hhmm):
    """Monotonic decimal hours from an 'HH:MM' string; pre-midday wraps to +24.
    '23:30' -> 23.5, '00:45' -> 24.75, '01:00' -> 25.0. None for empty input."""
    if not hhmm:
        return None
    h, m = (int(x) for x in str(hhmm).split(":")[:2])
    val = h + m / 60.0
    if h < 12:
        val += 24.0
    return round(val, 4)


# --- days ------------------------------------------------------------------
def upsert_day(day_date, values):
    """Insert or update a day; only provided columns are written."""
    cols = ["date"] + [c for c in DAY_COLUMNS if c in values]
    vals = [day_date] + [values[c] for c in DAY_COLUMNS if c in values]
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "date")
    with _conn() as conn:
        if not updates:
            conn.execute("INSERT OR IGNORE INTO days (date) VALUES (?)", (day_date,))
            return
        placeholders = ", ".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO days ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(date) DO UPDATE SET {updates}",
            vals,
        )


def get_day(day_date):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM days WHERE date=?", (day_date,)).fetchone()
    return dict(row) if row else None


def load_days_df():
    with _conn() as conn:
        return pd.read_sql_query("SELECT * FROM days ORDER BY date", conn)


def count_days():
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM days").fetchone()[0]


def clear_all():
    """Wipe everything (days, tasks, workouts)."""
    with _conn() as conn:
        conn.execute("DELETE FROM days")
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM workouts")


def clear_days():
    with _conn() as conn:
        conn.execute("DELETE FROM days")


def clear_workouts():
    with _conn() as conn:
        conn.execute("DELETE FROM workouts")


def delete_workouts_on(day_date):
    """Borra los workouts de UN día (para resincronizar solo esa fecha sin tocar
    el resto del historial)."""
    with _conn() as conn:
        conn.execute("DELETE FROM workouts WHERE date=?", (day_date,))


# --- workouts --------------------------------------------------------------
def insert_workout(values):
    cols = [c for c in WORKOUT_COLUMNS if c in values]
    placeholders = ", ".join("?" for _ in cols)
    with _conn() as conn:
        conn.execute(
            f"INSERT INTO workouts ({', '.join(cols)}) VALUES ({placeholders})",
            [values[c] for c in cols],
        )


def get_workouts(day_date):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM workouts WHERE date=? ORDER BY start", (day_date,)
        ).fetchall()
    return [dict(r) for r in rows]


# --- tasks -----------------------------------------------------------------
def get_tasks(day_date):
    # Orden: prioridad alta primero (3→1) y, a igualdad, por orden de creación.
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE date=? ORDER BY priority DESC, id", (day_date,)
        ).fetchall()
    return [dict(r) for r in rows]


def add_task(day_date, text, priority=2):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO tasks (date, text, done, priority) VALUES (?, ?, 0, ?)",
            (day_date, text, priority),
        )


def set_task_done(task_id, done):
    with _conn() as conn:
        conn.execute("UPDATE tasks SET done=? WHERE id=?", (1 if done else 0, task_id))


def set_task_priority(task_id, priority):
    with _conn() as conn:
        conn.execute("UPDATE tasks SET priority=? WHERE id=?", (priority, task_id))


def delete_task(task_id):
    with _conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))


def tasks_pct(day_date):
    """Porcentaje de tareas completadas PONDERADO por prioridad (alta=3, media=2,
    baja=1): las tareas importantes llenan más la barra."""
    tasks = get_tasks(day_date)
    if not tasks:
        return None
    total = sum((t.get("priority") or 2) for t in tasks)
    done = sum((t.get("priority") or 2) for t in tasks if t["done"])
    return round(done / total * 100, 1) if total else None
