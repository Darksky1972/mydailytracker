# 📡 Señal

App web local y de un solo usuario para registrar hábitos y tareas diarias,
importar tu biometría de Whoop y explorar las correlaciones entre ambos — para
separar **lo que de verdad mueve tu recovery** del ruido del día a día.

Hecha con **Streamlit + SQLite + pandas**. Funciona en local o en una VPS
pequeña (ver [`deploy/`](deploy/)).

---

## Qué hay en la app

Una sola página, de arriba abajo:

### Hoy
- **Cinco anillos** leídos de tu import de Whoop: Recovery, HRV, Strain, RHR y
  Sueño (con colores según el valor).
- **Registro de hábitos** — hábitos booleanos con casillas (entreno, estiramientos,
  journaling, leer, fap) y Japonés / Pantalla noche con sliders 0–120. (Cafeína,
  alcohol, siesta y hora de dormir se rellenan solos desde Whoop.)
- **Calendario NoFap** — rejilla del mes que marca con ✗ los días sin fap.
- **Tareas de hoy / para mañana** — planifica tareas; las de mañana aparecen
  solas en «hoy» cuando llega el día. El % completado del día se guarda.
- **Actividad de hoy** — minutos, calorías, FC media y minutos por zona de FC.

### Análisis
- Elige **Variable X / Y** (las booleanas van agrupadas aparte y las clave llevan ⭐).
- Interruptor **Lag +1 día** (por defecto ON): empareja hábito[D] con Whoop[D+1],
  porque las lecturas de la mañana reflejan la noche anterior. El Strain es del
  mismo día; Pantalla noche se desplaza (se registra a la mañana siguiente).
- **Nube de puntos** (coloreada por antigüedad) con recta de ajuste, **Pearson r**,
  etiqueta de fuerza y **n** (días emparejados). Avisa si n < 30.
- **Matriz de correlaciones** (exploratoria) — hábitos/actividad × métricas Whoop,
  con colores según el tema. Las variables secundarias se ocultan tras un toggle.

---

## Importar Whoop y alineación de fechas

Barra lateral → **Importar Whoop**: arrastra los CSV o déjalos en `data/` y pulsa
*Importar desde /data*. Archivos reconocidos (vale con un subconjunto):

| Archivo | Rellena |
| --- | --- |
| `physiological_cycles.csv` | Recovery, HRV, RHR, Day Strain, sueño + hora de dormir |
| `journal_entries.csv` | Hábitos del journal (estiramientos, leer, cafeína, alcohol…) |
| `workouts.csv` | Minutos, calorías, FC media/máx y minutos por zona de FC |
| `sleeps.csv` | Siestas (el hábito `siesta`) |

Un ciclo de Whoop junta el sueño de anoche con el strain de hoy, así que el
importador parte cada ciclo: Recovery/HRV/RHR/strain/sueño → **fecha de
despertar**; hora de dormir + journal → **fecha de inicio del ciclo**; workouts →
su fecha de inicio. Así `recovery[D]` sigue reflejando la noche de `D-1` y el lag
tiene sentido. Reimportar reemplaza los datos de Whoop pero **conserva tus campos
manuales** (Japonés, Pantalla noche, tareas).

---

## Ejecutar en local

Necesita Python 3.11+. Desde esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\streamlit run app.py
```

Se abre en http://localhost:8501. `senal.db` se crea solo; en el primer arranque
importa los CSV de `data/` si están. (En Windows también puedes hacer doble clic
en `run_senal.bat`.)

---

## Desplegar en un servidor

Ver **[deploy/DEPLOY.md](deploy/DEPLOY.md)**: deja la app detrás de Nginx con
**login + HTTPS**, como servicio systemd, y con actualizaciones por `git pull`.

---

## Archivos

| Archivo | Para qué |
| --- | --- |
| `app.py` | La página de Streamlit (Hoy + Análisis). |
| `db.py` | Esquema SQLite, upserts, consultas, grupos de variables, etiquetas. |
| `analysis.py` | Alineación de fechas + desplazamiento del lag, Pearson, fuerza, matriz. |
| `whoop_import.py` | Importador de los CSV de Whoop con el reparto de fechas del ciclo. |
| `requirements.txt` | Dependencias de Python. |
| `data/` | Deja aquí tus CSV de Whoop (excluido de git). |
| `deploy/` | Despliegue en VPS (systemd, Nginx, scripts y guía). |
| `senal.db` | Base de datos SQLite, creada en el primer arranque (excluida de git). |

---

## Privacidad

`senal.db` y `data/*.csv` son tus **datos personales de salud** y están
**excluidos de git** — nunca se suben a GitHub. Si la publicas, mantenla detrás
del login + HTTPS de la guía de despliegue.
