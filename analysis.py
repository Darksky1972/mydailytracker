"""Correlation analysis for Señal, including the temporal-lag alignment.

Whoop recovery is measured in the morning and reflects the PREVIOUS night, so a
habit done on day X shows up in the biometrics of the MORNING of day X+1. With
lag ON we therefore correlate habit[date] with whoop[date+1]; with lag OFF we
correlate same-day. The lag is implemented with a sorted, gap-filled daily
dataframe and pandas .shift(-1) on the Whoop columns.
"""
import numpy as np
import pandas as pd

from db import INPUT_VARS, WHOOP_VARS, LAGGED_VARS


def build_aligned(df, lag):
    """Return the days dataframe sorted by date, reindexed to a continuous
    daily range. When `lag` is True the Whoop columns are shifted by -1 so each
    habit row pairs with the NEXT calendar day's biometrics."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").set_index("date")

    # Reindex to every calendar day in range so .shift(-1) really means
    # "the next day" even if some days were never logged.
    full = pd.date_range(out.index.min(), out.index.max(), freq="D")
    out = out.reindex(full)

    if lag:
        # Shift the previous-night variables up by one day so habit[D] lines up
        # with whoop[D+1]. That's the morning readings (recovery/HRV/RHR/sleep…)
        # plus manual fields logged the next morning (pantalla_noche). Strain is
        # same-day and stays put; daytime habits are inputs and stay put.
        present = [c for c in LAGGED_VARS if c in out.columns]
        out[present] = out[present].shift(-1)

    return out.reset_index().rename(columns={"index": "date"})


def pearson(df, xcol, ycol):
    """Pearson r and n (paired, non-null days) for two columns.

    Returns (r, n). r is None when there aren't enough varying, paired points.
    """
    if df is None or df.empty or xcol not in df or ycol not in df:
        return None, 0
    sub = df[[xcol, ycol]].apply(pd.to_numeric, errors="coerce").dropna()
    n = len(sub)
    if n < 3 or sub[xcol].nunique() < 2 or sub[ycol].nunique() < 2:
        return None, n
    r = sub[xcol].corr(sub[ycol])
    return (None if pd.isna(r) else float(r)), n


def strength_label(r):
    """Plain-language strength + sign for a correlation coefficient."""
    if r is None:
        return "—"
    a = abs(r)
    if a < 0.1:
        return "nula"
    mag = "débil" if a < 0.3 else "moderada" if a < 0.5 else "fuerte"
    sign = "positiva" if r > 0 else "negativa"
    return f"{mag} {sign}"


def corr_matrix(df, lag):
    """Build the habits (rows) x whoop (cols) matrices of r and n."""
    aligned = build_aligned(df, lag)
    r_mat = pd.DataFrame(index=INPUT_VARS, columns=WHOOP_VARS, dtype=float)
    n_mat = pd.DataFrame(index=INPUT_VARS, columns=WHOOP_VARS, dtype=float)
    for h in INPUT_VARS:
        for w in WHOOP_VARS:
            r, n = pearson(aligned, h, w)
            r_mat.loc[h, w] = np.nan if r is None else r
            n_mat.loc[h, w] = n
    return r_mat, n_mat
