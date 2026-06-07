"""Synthetic seed data for Señal (Phase 1).

Plants ONE hidden relationship: an earlier bedtime on day D raises Whoop
recovery on the MORNING of day D+1. Every other habit is pure noise. Because
the signal is in the *next* day, it only appears with the análisis "lag +1"
toggle ON — and (correctly) vanishes with it OFF. That makes the seed a live
demonstration of why the lag matters.
"""
import random
from datetime import date, timedelta

import db


def _num_to_clock(num):
    """Wrapped decimal hours (e.g. 24.75) -> 'HH:MM' clock string ('00:45')."""
    h = int(num) % 24
    m = int(round((num - int(num)) * 60))
    if m == 60:
        m, h = 0, (h + 1) % 24
    return f"{h:02d}:{m:02d}"


def seed_synthetic(n_days=42, rng_seed=7):
    """Wipe and regenerate `n_days` of synthetic days ending today."""
    rng = random.Random(rng_seed)
    db.clear_all()

    today = date.today()
    start = today - timedelta(days=n_days - 1)
    prev_bt = None

    for i in range(n_days):
        d = start + timedelta(days=i)
        diso = d.isoformat()

        # Bedtime 22:30–01:30, snapped to the quarter hour.
        bt_num = round(rng.uniform(22.5, 25.5) * 4) / 4
        clock = _num_to_clock(bt_num)
        bt_num = db.bedtime_to_num(clock)  # keep it identical to the app's math

        # Planted signal: recovery depends on the PREVIOUS night's bedtime.
        # Earlier bedtime (smaller number) -> higher recovery, plus noise.
        if prev_bt is None:
            recovery = rng.gauss(60, 8)
        else:
            recovery = 60 - 11 * (prev_bt - 24.0) + rng.gauss(0, 7)
        recovery = max(5, min(99, recovery))

        # Other biometrics loosely track recovery (realism) but carry noise.
        hrv = max(15, 40 + 0.6 * (recovery - 60) + rng.gauss(0, 6))
        rhr = max(38, 60 - 0.12 * (recovery - 60) + rng.gauss(0, 3))
        strain = rng.uniform(7, 18)
        sleep_hours = max(4, min(9, rng.gauss(7.2, 0.9)))

        # Tasks %: real task rows only for today (so the Hoy list is populated);
        # past days just store a plausible percentage.
        total = rng.randint(2, 6)
        done = rng.randint(0, total)

        db.upsert_day(diso, {
            "entreno_manana": int(rng.random() < 0.5),
            "estiramientos": int(rng.random() < 0.5),
            "journaling": int(rng.random() < 0.5),
            "leer": int(rng.random() < 0.5),
            "fap": int(rng.random() < 0.5),
            "japones_min": rng.choice([0, 0, 15, 20, 30, 45, 60]),
            "pantalla_noche_min": rng.choice([0, 15, 30, 45, 60, 90, 120]),
            "hora_dormir": clock,
            "hora_dormir_num": bt_num,
            "tareas_pct": round(done / total * 100, 1),
            "recovery": round(recovery, 1),
            "strain": round(strain, 1),
            "hrv": round(hrv, 1),
            "rhr": round(rhr, 1),
            "sleep_hours": round(sleep_hours, 1),
        })

        if i == n_days - 1:  # today: materialise real task rows
            for k in range(total):
                db.add_task(diso, f"Tarea de ejemplo {k + 1}")
            for t in db.get_tasks(diso)[:done]:
                db.set_task_done(t["id"], True)
            db.upsert_day(diso, {"tareas_pct": db.tasks_pct(diso)})

        prev_bt = bt_num

    db.set_meta("data_source", "synthetic")   # so a real import knows to replace it
