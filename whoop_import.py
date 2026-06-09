"""Whoop CSV importer for Señal (Phase 2).

Maps a Whoop data export onto Señal's one-row-per-calendar-day model. The tricky
part is date alignment, because a Whoop "cycle" bundles last night's sleep with
today's strain:

  * physiological_cycles.csv → recovery / HRV / RHR / strain / sleep are stored
    under the WAKE date (the morning they were measured, reflecting the night
    before). This keeps the app's convention "recovery[D] reflects the night of
    D-1" intact, so the lag toggle works.
  * Bedtime (`hora_dormir`) is a habit you perform on day D → stored under the
    CYCLE START date.
  * journal_entries.csv (filled at bedtime, describing the day that just ended)
    → stored under the CYCLE START date.
  * workouts.csv → stored under the workout's start date.
  * sleeps.csv → used only to flag naps (`siesta`).

Accepts file paths or file-like objects (e.g. Streamlit UploadedFile).
"""
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import pandas as pd

import db

# Whoop journal question -> Señal habit field (only the high-signal ones).
JOURNAL_MAP = {
    "Spent time stretching?": "estiramientos",
    "Journaled your thoughts?": "journaling",
    "Read (non-screened device) while in bed?": "leer",
    "Masturbated?": "fap",
    "Consumed caffeine?": "cafeina",
    "Have any alcoholic drinks?": "alcohol",
}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _set(rec, key, val):
    n = _num(val)
    if n is not None:
        rec[key] = n


def _dt(v):
    return pd.to_datetime(v, errors="coerce")


def _cycle_day(ts):
    """Calendar day a Whoop cycle (and its bedtime/journal) belongs to.

    A sleep that starts after midnight but before noon belongs to the PREVIOUS
    day — the day you actually lived and went to bed — so it lines up with the
    rest of that day's habits. (Equivalent to wake_date - 1 for normal sleeps.)
    """
    if pd.isna(ts):
        return None
    d = ts.date()
    if ts.hour < 12:
        d -= timedelta(days=1)
    return d.isoformat()


def import_whoop(physio=None, journal=None, workouts=None, sleeps=None, wipe=True):
    """Import any subset of the four Whoop CSVs. Returns a summary dict."""
    by_date = defaultdict(dict)        # date -> partial day record
    workout_rows = []

    # --- physiological cycles: biometrics @ wake date, bedtime @ start date ---
    if physio is not None:
        for _, r in pd.read_csv(physio).iterrows():
            wake = _dt(r.get("Wake onset"))
            if pd.notna(wake):
                rec = by_date[wake.date().isoformat()]
                _set(rec, "recovery", r.get("Recovery score %"))
                _set(rec, "rhr", r.get("Resting heart rate (bpm)"))
                _set(rec, "hrv", r.get("Heart rate variability (ms)"))
                _set(rec, "strain", r.get("Day Strain"))
                # gasto energético total del día (ya viene en kcal en el CSV)
                _set(rec, "calories_burned", r.get("Energy burned (cal)"))
                asleep = _num(r.get("Asleep duration (min)"))
                if asleep is not None:
                    rec["sleep_hours"] = round(asleep / 60, 2)
                _set(rec, "sleep_performance", r.get("Sleep performance %"))
                _set(rec, "resp_rate", r.get("Respiratory rate (rpm)"))
                _set(rec, "skin_temp", r.get("Skin temp (celsius)"))
                _set(rec, "spo2", r.get("Blood oxygen %"))
            onset = _dt(r.get("Sleep onset"))
            if pd.notna(onset):
                clock = onset.strftime("%H:%M")
                rec2 = by_date[_cycle_day(onset)]   # the day you went to bed
                rec2["hora_dormir"] = clock
                rec2["hora_dormir_num"] = db.bedtime_to_num(clock)

    # --- journal: habits @ cycle start date ---
    if journal is not None:
        for _, r in pd.read_csv(journal).iterrows():
            start = _dt(r.get("Cycle start time"))
            field = JOURNAL_MAP.get(str(r.get("Question text", "")).strip())
            if pd.isna(start) or not field:
                continue
            yes = str(r.get("Answered yes", "")).strip().lower() == "true"
            by_date[_cycle_day(start)][field] = int(yes)   # day the journal describes

    # --- workouts: aggregate per workout start date ---
    if workouts is not None:
        agg = defaultdict(lambda: {"min": 0.0, "cal": 0.0, "hr_sum": 0.0,
                                   "max": 0.0, "z": [0.0] * 5, "acts": [],
                                   "count": 0, "morning": False})
        for _, r in pd.read_csv(workouts).iterrows():
            ws = _dt(r.get("Workout start time"))
            if pd.isna(ws):
                continue
            d = ws.date().isoformat()
            dur = _num(r.get("Duration (min)")) or 0.0
            avg = _num(r.get("Average HR (bpm)")) or 0.0
            zmin = [round(dur * (_num(r.get(f"HR Zone {i+1} %")) or 0) / 100, 1)
                    for i in range(5)]
            a = agg[d]
            a["min"] += dur
            a["cal"] += _num(r.get("Energy burned (cal)")) or 0.0
            a["hr_sum"] += avg * dur
            a["max"] = max(a["max"], _num(r.get("Max HR (bpm)")) or 0.0)
            a["count"] += 1
            a["morning"] = a["morning"] or ws.hour < 12
            for i in range(5):
                a["z"][i] += zmin[i]
            name = str(r.get("Activity name", "")).strip()
            if name and name not in a["acts"]:
                a["acts"].append(name)
            workout_rows.append({
                "date": d, "start": ws.strftime("%H:%M"), "activity": name,
                "duration_min": dur, "calories": _num(r.get("Energy burned (cal)")),
                "avg_hr": avg or None, "max_hr": _num(r.get("Max HR (bpm)")),
                "strain": _num(r.get("Activity Strain")),
                **{f"z{i+1}_min": zmin[i] for i in range(5)},
            })
        for d, a in agg.items():
            rec = by_date[d]
            rec["workout_min"] = round(a["min"], 1)
            rec["workout_calories"] = round(a["cal"])
            rec["workout_avg_hr"] = round(a["hr_sum"] / a["min"]) if a["min"] else None
            rec["workout_max_hr"] = a["max"] or None
            rec["workout_count"] = a["count"]
            rec["entreno_manana"] = int(a["morning"])
            rec["activities"] = ", ".join(a["acts"])
            for i in range(5):
                rec[f"hr_zone{i+1}_min"] = round(a["z"][i], 1)

    # --- sleeps: naps -> siesta habit @ nap date ---
    if sleeps is not None:
        for _, r in pd.read_csv(sleeps).iterrows():
            if str(r.get("Nap", "")).strip().lower() != "true":
                continue
            onset = _dt(r.get("Sleep onset"))
            if pd.notna(onset):
                by_date[onset.date().isoformat()]["siesta"] = 1

    # --- write ---
    # Preserve manual-only data across re-imports. We only wipe `days` the FIRST
    # time we move off synthetic data; afterwards we MERGE (upsert), so columns
    # the import never touches — japones_min, pantalla_noche_min, tareas_pct and
    # the tasks table — survive. Workouts are 100% Whoop-derived, so we clear and
    # rebuild them (when a workouts file is given) to avoid duplicates.
    if wipe:
        if db.get_meta("data_source") != "whoop":
            db.clear_days()
        if workouts is not None:
            db.clear_workouts()
        db.set_meta("seeded", "1")
        db.set_meta("data_source", "whoop")
    for d, rec in by_date.items():
        db.upsert_day(d, rec)
    for w in workout_rows:
        db.insert_workout(w)

    return {"days": len(by_date), "workouts": len(workout_rows)}


# Known Whoop export filenames, for one-click import from the project folder.
KNOWN_FILES = {
    "physio": "physiological_cycles.csv",
    "journal": "journal_entries.csv",
    "workouts": "workouts.csv",
    "sleeps": "sleeps.csv",
}


def import_from_folder(folder, wipe=True):
    """Import whichever known Whoop CSVs are present in `folder`."""
    folder = Path(folder)
    found = {k: folder / fn for k, fn in KNOWN_FILES.items() if (folder / fn).exists()}
    if not found:
        return None
    return import_whoop(
        physio=found.get("physio"), journal=found.get("journal"),
        workouts=found.get("workouts"), sleeps=found.get("sleeps"), wipe=wipe,
    )
