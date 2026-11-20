"""
evaluate.py -- hitter-season table, reliability and validity, raw vs contact-adjusted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import contact_model as cm


# ------------------------------------------------------------------ adjusted per-swing columns

def add_adjusted_columns(sw: pd.DataFrame, ref: dict, outcomes=("bat_speed", "swing_length", "impulse"),
                         surface_kwargs: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Fit a within-hitter surface per outcome and add *_adj (contact) and *_adjfull (contact+context)."""
    sw = sw.copy()
    surfaces = {}
    for y in outcomes:
        s = cm.Surface(**(surface_kwargs or {})).fit(sw, y)
        f_ref = float(s.f(sw).mean())
        sw[f"{y}_adj"] = cm.adjust(sw, y, s, f_ref)
        sw[f"{y}_adjfull"] = cm.adjust(sw, y, s, f_ref, remove_context=True)
        sw[f"{y}_adjfull"] += sw[y].mean() - sw[f"{y}_adjfull"].mean()   # keep league level
        surfaces[y] = s
    if "bat_speed_adj" in sw:
        sw["contact_effect"] = sw["bat_speed"] - sw["bat_speed_adj"]  # mph credited to contact point
    return sw, surfaces


def hitter_table(sw: pd.DataFrame, outcomes_df: pd.DataFrame) -> pd.DataFrame:
    g = sw.groupby("hs")
    t = pd.DataFrame({
        "n": g.size(),
        "bat_speed": g["bat_speed"].mean(),
        "bat_speed_adj": g["bat_speed_adj"].mean(),
        "bat_speed_adjfull": g["bat_speed_adjfull"].mean(),
        "bat_speed_p90": g["bat_speed"].quantile(0.9),
        "bat_speed_adj_p90": g["bat_speed_adj"].quantile(0.9),
        "swing_length": g["swing_length"].mean(),
        "swing_length_adj": g["swing_length_adj"].mean(),
        "impulse": g["impulse"].mean(),
        "impulse_adj": g["impulse_adj"].mean(),
        "contact_effect": g["contact_effect"].mean(),
        "depth": g["depth"].mean(),
        "depth_ms": g["depth_ms"].mean(),
        "offbody": g["offbody"].mean(),
        "bat_speed_sd": g["bat_speed"].std(),
        "bat_speed_adj_sd": g["bat_speed_adj"].std(),
    })
    t["length_per_mph"] = t["swing_length"] / t["bat_speed"]
    t["length_per_mph_adj"] = t["swing_length_adj"] / t["bat_speed_adj"]
    return t.join(outcomes_df, how="left")


# ------------------------------------------------------------------ reliability

def stabilization(sw: pd.DataFrame, metrics: list[str], grid=(10, 20, 30, 40, 50, 75, 100, 150, 200, 300),
                  min_swings: int = 400) -> pd.DataFrame:
    """Two curves per metric, for hitter-seasons with >= min_swings (in game order):

    r_full : first-n mean vs full-season mean (the 2.0 definition, overlapping samples)
    r_rest : first-n mean vs the mean of all *later* swings (no overlap; stricter)
    """
    elig = sw.groupby("hs").filter(lambda d: len(d) >= min_swings)
    elig = elig.assign(k=elig.groupby("hs").cumcount())
    rows = []
    for m in metrics:
        full = elig.groupby("hs")[m].mean()
        for n in grid:
            first = elig[elig["k"] < n].groupby("hs")[m].mean()
            rest = elig[elig["k"] >= n].groupby("hs")[m].mean()
            rows.append({"metric": m, "n": n, "r_full": first.corr(full), "r_rest": first.corr(rest),
                         "hitters": len(full)})
    return pd.DataFrame(rows)


def swings_to_threshold(stab: pd.DataFrame, col: str = "r_full", thr: float = 0.9) -> dict:
    """Interpolated number of swings where the curve first reaches thr."""
    out = {}
    for m, d in stab.groupby("metric"):
        d = d.sort_values("n")
        above = d[d[col] >= thr]
        if above.empty:
            out[m] = np.nan
            continue
        i = d.index.get_loc(above.index[0])
        if i == 0:
            out[m] = float(d["n"].iloc[0])
            continue
        n0, n1 = d["n"].iloc[i - 1], d["n"].iloc[i]
        r0, r1 = d[col].iloc[i - 1], d[col].iloc[i]
        out[m] = float(n0 + (thr - r0) / (r1 - r0) * (n1 - n0))
    return out


def split_half(sw: pd.DataFrame, metrics: list[str], min_swings: int = 150) -> pd.Series:
    """Odd/even split-half reliability, Spearman-Brown corrected."""
    d = sw.groupby("hs").filter(lambda x: len(x) >= min_swings)
    d = d.assign(half=d.groupby("hs").cumcount() % 2)
    out = {}
    for m in metrics:
        p = d.pivot_table(index="hs", columns="half", values=m, aggfunc="mean")
        r = p[0].corr(p[1])
        out[m] = 2 * r / (1 + r)
    return pd.Series(out)


def year_over_year(tab: pd.DataFrame, metrics: list[str], min_n: int = 200) -> pd.DataFrame:
    t = tab[tab["n"] >= min_n].reset_index()
    rows = []
    seasons = sorted(t["season"].unique())
    for s0, s1 in zip(seasons[:-1], seasons[1:]):
        a = t[t["season"] == s0].set_index("batter")
        b = t[t["season"] == s1].set_index("batter")
        both = a.index.intersection(b.index)
        for m in metrics:
            rows.append({"pair": f"{s0}->{s1}", "metric": m, "r": a.loc[both, m].corr(b.loc[both, m]),
                         "hitters": len(both)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ validity

def paired_seasons(tab: pd.DataFrame, min_n: int) -> pd.DataFrame:
    """Rows = hitter with season s metrics and season s+1 outcomes (suffix _next)."""
    t = tab[tab["n"] >= min_n].reset_index()
    nxt = t.copy()
    nxt["season"] = nxt["season"] - 1
    return t.merge(nxt, on=["batter", "season"], suffixes=("", "_next"))


def corr_table(df: pd.DataFrame, metrics: list[str], outcomes: list[str], suffix: str = "") -> pd.DataFrame:
    return pd.DataFrame({o: [df[m].corr(df[o + suffix]) for m in metrics] for o in outcomes}, index=metrics)


def bootstrap_diff(df: pd.DataFrame, a: str, b: str, outcome: str, n_boot: int = 2000,
                   seed: int = 0) -> tuple[float, float, float]:
    """r(b, outcome) - r(a, outcome) with a 95% CI from resampling hitters (clusters)."""
    rng = np.random.default_rng(seed)
    d = df[[a, b, outcome, "batter"]].dropna()
    groups = d.groupby("batter").indices
    keys = np.array(list(groups))
    idx = [groups[k] for k in keys]
    A, B, O = d[a].to_numpy(), d[b].to_numpy(), d[outcome].to_numpy()
    point = np.corrcoef(B, O)[0, 1] - np.corrcoef(A, O)[0, 1]
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        take = np.concatenate([idx[j] for j in rng.integers(0, len(keys), len(keys))])
        diffs[i] = np.corrcoef(B[take], O[take])[0, 1] - np.corrcoef(A[take], O[take])[0, 1]
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return point, lo, hi


def incremental_r2(df: pd.DataFrame, base: list[str], add: list[str], outcome: str) -> dict:
    """R^2 of outcome on base, and on base+add (plain OLS)."""
    d = df[base + add + [outcome]].dropna()

    def r2(cols):
        X = np.column_stack([np.ones(len(d))] + [d[c] for c in cols])
        beta = np.linalg.lstsq(X, d[outcome], rcond=None)[0]
        res = d[outcome] - X @ beta
        return 1 - res.var() / d[outcome].var()

    return {"r2_base": r2(base), "r2_full": r2(base + add), "n": len(d)}
