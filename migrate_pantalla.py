"""Migración ÚNICA: desplaza el histórico de 'pantalla_noche_min' un día atrás.

Antes se registraba a la mañana siguiente (el valor del día R pertenecía en
realidad a la noche del día R-1) y se corregía con el lag. Ahora el lag está
quitado y se registra en su día real, así que movemos cada valor de su día R al
día R-1.  Es idempotente: solo actúa una vez (marca un flag en `meta`).

Uso:  /opt/senal/.venv/bin/python /opt/senal/migrate_pantalla.py
"""
import sys
from datetime import date, timedelta

import db

FLAG = "pantalla_shift_v1"


def main():
    db.init_db()
    if db.get_meta(FLAG):
        print("Ya estaba hecho (flag pantalla_shift_v1). No se toca nada.")
        return 0

    df = db.load_days_df()
    old = {}
    if not df.empty and "pantalla_noche_min" in df.columns:
        for _, row in df.iterrows():
            v = row["pantalla_noche_min"]
            if v is not None and not (isinstance(v, float) and v != v):   # no NaN
                old[row["date"]] = int(v)

    if not old:
        db.set_meta(FLAG, "1")
        print("Sin valores de pantalla_noche; nada que migrar.")
        return 0

    # Fechas a tocar: las que tenían valor (para limpiarlas/reescribirlas) y el día
    # anterior de cada una (que recibe el valor desplazado).
    affected = set(old) | {(date.fromisoformat(d) - timedelta(days=1)).isoformat()
                           for d in old}
    moved = 0
    for e in affected:
        nxt = (date.fromisoformat(e) + timedelta(days=1)).isoformat()
        new_val = old.get(nxt)          # el valor que estaba en el día siguiente
        db.upsert_day(e, {"pantalla_noche_min": new_val})
        if new_val is not None:
            moved += 1

    db.set_meta(FLAG, "1")
    print(f"Listo: {moved} valores de pantalla_noche desplazados un día atrás.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
