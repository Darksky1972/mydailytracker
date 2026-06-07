# 📡 Señal

A local, single-user web app to log daily habits and tasks, record Whoop
biometrics, and explore correlations between them — so you can separate what
actually moves your recovery from daily noise.

**Phase 2** is in: Whoop metrics, sleep, journaled habits and workouts are now
imported from a Whoop CSV export (manual Whoop entry has been removed). The
Whoop OAuth auto-pull (Phase 3) comes later.

---

## Importing your Whoop data

From the **sidebar → Importar Whoop**, either drag in the CSVs from your Whoop
export, or drop them next to `app.py` and click *Importar desde la carpeta*.
Recognised files (any subset works):

| File | What it fills |
| --- | --- |
| `physiological_cycles.csv` | Recovery, HRV, RHR, Day Strain, sleep hours + bedtime |
| `journal_entries.csv` | Habits (stretching, journaling, reading, caffeine, alcohol…) |
| `workouts.csv` | Per-day activity minutes, calories, avg/max HR, HR-zone minutes |
| `sleeps.csv` | Naps (the `siesta` habit) |

**Date alignment (the important bit).** A Whoop cycle bundles last night's sleep
with today's strain, so the importer splits each cycle:
- Recovery / HRV / RHR / strain / sleep → stored under the **wake date** (the
  morning they were measured, reflecting the night before).
- Bedtime and the journal (filled at night about the day that just ended) →
  stored under the **cycle-start date**.
- Workouts → the workout's start date.

This keeps the app's convention intact (`recovery[D]` reflects the night of
`D-1`), so the **lag +1** toggle still means "what I did on day D → how I
recover the morning of D+1". Importing replaces the current data but keeps your
manually-entered tasks.

---

## Requirements

- **Python 3.11+** — not currently installed on this machine. The `python`
  command on this PC only opens the Microsoft Store stub. Install a real Python
  from https://www.python.org/downloads/ (tick *"Add python.exe to PATH"* in the
  installer), then open a **new** terminal so the PATH change takes effect.

Verify it works:

```powershell
python --version    # should print Python 3.11.x or newer
```

## Setup & run

From this folder (`Tracker`):

```powershell
# 1. (recommended) create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. install dependencies
pip install -r requirements.txt

# 3. run the app
streamlit run app.py
```

Streamlit opens the app in your browser (usually http://localhost:8501).
The SQLite database `senal.db` is created automatically in this folder, and on
first run it is seeded with ~42 days of synthetic data so the analysis has
something to show immediately.

---

## What's in the app

A single page, top to bottom:

### Hoy (today)
- **Three gauges** — Recovery /100 (green ≥ 67, amber 34–66, red < 34),
  Strain /21, Sleep /9h — plus HRV and RHR as numbers.
- **Habit logger** — the five boolean habits as toggles, Japonés and Pantalla
  noche as number inputs, and **Hora de dormir** as a time picker. Bedtime is
  also stored as a monotonic decimal (`23:30 → 23.5`, `00:45 → 24.75`) so
  "later bedtime" is always a bigger number for correlation.
- **Task list** — add tasks, check them off, see a live completion %.
  `tareas_pct` for the day = done / total × 100, and is saved with the day.
- **Guardar hoy** upserts the day into SQLite (keyed by date).

### Análisis
- **Variable X / Variable Y** dropdowns over every habit + Whoop metric.
- **Lag +1 día** toggle (default **ON**): habit[date] is correlated with
  whoop[date+1] because Whoop recovery is measured in the morning and reflects
  the *previous* night. Turn it off for same-day correlation.
- **Scatter** of the chosen pair with a fit line, the **Pearson r** as a big
  number, a plain-language strength label (nula / débil / moderada / fuerte),
  and **n** (paired days).
- **Correlation matrix** — habits (rows) × Whoop metrics (columns), color-coded
  red (negative) → blue (positive).

### Statistical guardrails (shown, not hidden)
- **n** is displayed next to every correlation.
- If **n < 30**, a visible warning says results may be noise.
- The matrix is labelled **exploratory** — it runs many simultaneous tests, so
  some cells will look strong by chance. Nothing here implies causality.

### The built-in demo
The synthetic seed plants exactly one hidden relationship: an **earlier bedtime
raises the next day's recovery**. Everything else is noise. So:

- X = **Hora de dormir**, Y = **Recovery**, lag **ON** → a clear negative
  correlation appears.
- The same pair with lag **OFF** → it disappears.

That is the whole point of the lag toggle, demonstrated live.

### Data management (sidebar)
- **Reset + datos sintéticos** — wipe and regenerate the synthetic dataset.
- **Borrar todo** — clear all data (and it stays empty; it won't re-seed).

---

## Files

| File             | Purpose                                                        |
| ---------------- | -------------------------------------------------------------- |
| `app.py`         | The Streamlit page (Hoy + Análisis).                           |
| `db.py`          | SQLite schema, upserts, queries, bedtime→decimal, labels.      |
| `analysis.py`    | Date alignment + `.shift(-1)` lag, Pearson, strength, matrix.  |
| `seed.py`        | 42-day synthetic seed with the planted bedtime→recovery signal.|
| `requirements.txt` | Python dependencies.                                         |
| `senal.db`       | SQLite database (created on first run; git-ignored).           |

## Data model

`days` — one row per ISO date (`yyyy-mm-dd`, primary key):
habits `entreno_manana, estiramientos, journaling, leer, fap` (bool),
`japones_min, pantalla_noche_min` (int), `hora_dormir` (text) +
`hora_dormir_num` (decimal), `tareas_pct` (derived), and Whoop
`recovery, strain, hrv, rhr, sleep_hours`.

`tasks` — `id, date, text, done`.

`meta` — internal key/value (tracks the one-time seed).
