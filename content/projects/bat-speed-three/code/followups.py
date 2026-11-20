"""
followups.py -- follow-up tests (Oct 2026) behind the acceleration discussion on X with
Doyoung-Tom Kim (@tomdoyo). Not part of the published page; FOLLOWUPS.md summarizes the results.

    python followups.py                                   # data from ../../savant_out
    python followups.py --data a.parquet b.parquet c.parquet

Rebuilds the page's competitive-swing set (same filters, same contact surfaces as run_all.py) and
writes results/followups.json + results/followups_report.txt. A few minutes on a laptop.
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

import contact_model as cm
import evaluate as ev
import prep
import tradeoff as tr
from extras import cv_r2

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
DEFAULT_DATA = [HERE.parents[1] / "savant_out" / f"swings_{y}.parquet" for y in (2024, 2025, 2026)]
OUTCOMES = ["barrel_rate", "ev50", "hardhit_rate", "xwobacon", "whiff_rate"]
MIN_N = 150
LINES: list[str] = []
R: dict = {}


def out(s: str = "") -> None:
    print(s, flush=True)
    LINES.append(s)


def partial(d: pd.DataFrame, a: str, b: str, ctrls: list[str]) -> float:
    d = d[[a, b] + ctrls].dropna()
    X = np.column_stack([np.ones(len(d))] + [d[x] for x in ctrls])
    res = lambda y: d[y] - X @ np.linalg.lstsq(X, d[y], rcond=None)[0]
    return float(res(a).corr(res(b)))


def crossing(rs: list[float], grid: list[int], thr: float = 0.9) -> float:
    """Interpolated n where the curve first reaches thr."""
    for i in range(1, len(grid)):
        if rs[i] >= thr > rs[i - 1]:
            return float(grid[i - 1] + (thr - rs[i - 1]) / (rs[i] - rs[i - 1]) * (grid[i] - grid[i - 1]))
    return float("nan")


def pairs_next(t: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Season s rows joined to the same hitter's season s+1 values (suffix _next); both seasons must be in t."""
    cur = t.reset_index().set_index(["batter", "season"])
    nxt = cur[cols].rename(index=lambda s: s - 1, level="season")
    return cur.join(nxt, rsuffix="_next", how="inner").reset_index()


def oos_pred(d: pd.DataFrame, xs: list[str], y: str, seed: int, k: int = 10) -> np.ndarray:
    """Same batter-grouped folds as extras.cv_r2, returning the out-of-sample predictions."""
    rng = np.random.default_rng(seed)
    bat = d["batter"].unique()
    f = d["batter"].map(dict(zip(bat, rng.integers(0, k, len(bat))))).to_numpy()
    pred = np.empty(len(d))
    for i in range(k):
        trn, tst = d[f != i], d[f == i]
        b = np.linalg.lstsq(np.column_stack([np.ones(len(trn))] + [trn[x] for x in xs]), trn[y], rcond=None)[0]
        pred[f == i] = np.column_stack([np.ones(len(tst))] + [tst[x] for x in xs]) @ b
    return pred


def sq_err(d: pd.DataFrame, xs: list[str], y: str, n_splits: int = 20) -> np.ndarray:
    yv = d[y].to_numpy()
    return np.mean([(yv - oos_pred(d, xs, y, s)) ** 2 for s in range(n_splits)], axis=0)


def boot_gain(se_a, se_b, yv, batters, rng, n_boot=1000) -> tuple[float, float, float]:
    """R^2 gain (x1000) of model b over model a; 95% CI from resampling batters."""
    ub = np.unique(batters)
    idx = {b: np.where(batters == b)[0] for b in ub}
    g = lambda ii: 1000 * (se_a[ii].mean() - se_b[ii].mean()) / yv[ii].var()
    draws = [g(np.concatenate([idx[b] for b in rng.choice(ub, len(ub))])) for _ in range(n_boot)]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(g(np.arange(len(yv)))), float(lo), float(hi)


# ------------------------------------------------------------------------------------------ build
def build(paths):
    raw = prep.load([str(p) for p in paths])
    base, audit = prep.base_filter(raw)
    del raw
    outc = prep.outcomes(base)
    sw = prep.tracked_swings(base, audit)
    g = sw.groupby("hs")["bat_speed"]
    q1, q3 = g.transform(lambda s: s.quantile(.25)), g.transform(lambda s: s.quantile(.75))
    sw["iqr_floor"] = q1 - 1.5 * (q3 - q1)
    comp = sw[sw["competitive_iqr"]].reset_index(drop=True)
    ref = cm.reference_point(comp)
    comp, surfaces = ev.add_adjusted_columns(comp, ref, outcomes=("bat_speed", "swing_length"))
    L, v = comp["swing_length"].clip(lower=0.5), comp["bat_speed"]
    La, va = comp["swing_length_adj"].clip(lower=0.5), comp["bat_speed_adj"]
    comp["lv"], comp["vl"], comp["acc"] = L / v, v / L, v ** 2 / L
    comp["lv_a"], comp["vl_a"], comp["acc_a"] = La / va, va / La, va ** 2 / La
    return comp, outc, sw, ref, surfaces


def hitter_table(comp, outc):
    g = comp.groupby("hs")
    t = pd.DataFrame({
        "n": g.size(), "batter": g["batter"].first(), "season": g["season"].first(),
        "bs": g["bat_speed"].mean(), "bs_adj": g["bat_speed_adj"].mean(), "depth": g["depth_ms"].mean(),
        "ce": g["contact_effect"].mean(),
        "L": g["swing_length"].mean(), "L_adj": g["swing_length_adj"].mean(),
        "LV_ps": g["lv"].mean(), "LV_ps_adj": g["lv_a"].mean(), "VL_ps": g["vl"].mean(), "VL_ps_adj": g["vl_a"].mean(),
        "acc": g["acc"].mean(), "acc_adj": g["acc_a"].mean(),
    })
    t["LV"] = t["L"] / t["bs"]                # season-level ratio, as evaluate.hitter_table's length_per_mph
    t["LV_adj"] = t["L_adj"] / t["bs_adj"]
    return t.join(outc[OUTCOMES], how="left")


# ------------------------------------------------------------------------------------------ sections
def stabilization(comp):
    out("=" * 100)
    out("1. STABILIZATION -- swings until the first-n average reaches r = .90 (hitter-seasons with 400+ swings)")
    out("   full = vs full-season average (the page's / 2.0's method); rest = vs rest of season, no overlap")
    out("=" * 100)
    el = comp.groupby("hs").filter(lambda d: len(d) >= 400)
    el = el.assign(k=el.groupby("hs").cumcount())
    grid = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100]
    specs = {
        "raw bat speed": ("mean", "bat_speed"),
        "adjusted bat speed": ("mean", "bat_speed_adj"),
        "raw acceleration (v^2/L)": ("mean", "acc"),
        "adjusted acceleration (v^2/L)": ("mean", "acc_a"),
        "raw length/speed (season ratio)": ("ratio", ("swing_length", "bat_speed")),
        "adjusted length/speed (season ratio)": ("ratio", ("swing_length_adj", "bat_speed_adj")),
        "raw length/speed (per-swing mean)": ("mean", "lv"),
        "adjusted length/speed (per-swing mean)": ("mean", "lv_a"),
        "raw length/speed (per-swing median)": ("median", "lv"),
        "adjusted speed/length v/L (per-swing)": ("mean", "vl_a"),
    }

    def agg(d, spec):
        kind, col = spec
        g = d.groupby("hs")
        if kind == "ratio":
            return g[col[0]].mean() / g[col[1]].mean()
        return g[col].median() if kind == "median" else g[col].mean()

    R["stabilization"] = {}
    out("   %-42s %8s %8s" % ("metric", "full", "rest"))
    for name, spec in specs.items():
        full_mean = agg(el, spec)
        r_full = [agg(el[el.k < n], spec).corr(full_mean) for n in grid]
        r_rest = [agg(el[el.k < n], spec).corr(agg(el[el.k >= n], spec)) for n in grid]
        f, r = crossing(r_full, grid), crossing(r_rest, grid)
        R["stabilization"][name] = {"full": f, "rest": r}
        out("   %-42s %8.1f %8.1f" % (name, f, r))
    out("   hitter-seasons: %d" % el["hs"].nunique())


def hitter_level(t):
    q = t[t.n >= MIN_N]
    p = pairs_next(q, OUTCOMES + ["bs", "bs_adj", "depth", "LV", "LV_adj", "acc", "acc_adj", "ce"])
    out()
    out("=" * 100)
    out("2. HITTER-SEASON RELATIONSHIPS (%d hitter-seasons with %d+ competitive swings; %d next-season pairs)" % (len(q), MIN_N, len(p)))
    out("=" * 100)
    A = {}
    out("   a) correlation with bat speed (raw metrics vs raw speed, adjusted vs adjusted speed)")
    for m, s in (("LV", "bs"), ("LV_adj", "bs_adj"), ("acc", "bs"), ("acc_adj", "bs_adj"), ("VL_ps_adj", "bs_adj")):
        A[f"corr_{m}_speed"] = float(q[m].corr(q[s]))
        out("      %-10s %+.3f" % (m, A[f"corr_{m}_speed"]))
    out("   b) year over year")
    for m in ("bs", "bs_adj", "acc", "acc_adj", "LV", "LV_adj"):
        A[f"yoy_{m}"] = float(p[m].corr(p[m + "_next"]))
        out("      %-10s %.3f" % (m, A[f"yoy_{m}"]))
    out("   c) per-swing vs season-level ratios")
    A["corr_LV_season_vs_perswing"] = float(q["LV"].corr(q["LV_ps"]))
    A["corr_LVadj_season_vs_perswing"] = float(q["LV_adj"].corr(q["LV_ps_adj"]))
    A["corr_LV_perswing_vs_VL_perswing"] = float(q["LV_ps"].corr(q["VL_ps"]))
    out("      L/v season vs per-swing mean:          %.3f (adjusted: %.3f)" % (A["corr_LV_season_vs_perswing"], A["corr_LVadj_season_vs_perswing"]))
    out("      per-swing L/v vs per-swing v/L:        %.3f" % A["corr_LV_perswing_vs_VL_perswing"])
    out("   d) correlation with average contact depth (ms; + = further out front)")
    A["corr_bs_depth"], A["corr_bsadj_depth"] = float(q.bs.corr(q.depth)), float(q.bs_adj.corr(q.depth))
    out("      raw bat speed %+.2f | adjusted bat speed %+.2f" % (A["corr_bs_depth"], A["corr_bsadj_depth"]))
    out("      %-10s %8s %20s %20s" % ("", "plain", "ctrl adjusted speed", "ctrl raw speed"))
    for m in ("LV_adj", "acc_adj", "LV", "acc"):
        row = (float(q[m].corr(q.depth)), partial(q, m, "depth", ["bs_adj"]), partial(q, m, "depth", ["bs"]))
        A[f"depth_{m}"] = dict(zip(("plain", "ctrl_adj_speed", "ctrl_raw_speed"), row))
        out("      %-10s %+8.2f %+20.2f %+20.2f" % (m, *row))
    out("   e) adjusted L/v vs adjusted acceleration: same information once bat speed is held fixed?")
    A["LVadj_vs_accadj"] = {"plain": float(q.LV_adj.corr(q.acc_adj)),
                            "ctrl_adj_speed": partial(q, "LV_adj", "acc_adj", ["bs_adj"]),
                            "ctrl_raw_speed": partial(q, "LV_adj", "acc_adj", ["bs"])}
    out("      plain %+.3f | holding adjusted speed fixed %+.3f | holding raw speed fixed %+.3f" % tuple(A["LVadj_vs_accadj"].values()))
    out("   f) why length/speed comes out ~independent of speed: path length scales with speed across hitters")
    A["corr_Ladj_bsadj"] = float(q.L_adj.corr(q.bs_adj))
    A["path_scaling_exponent"] = float(np.polyfit(np.log(q.bs_adj), np.log(q.L_adj), 1)[0])
    out("      corr(adjusted path length, adjusted speed) %+.2f; path ~ speed^%.2f (1.00 = proportional)" % (A["corr_Ladj_bsadj"], A["path_scaling_exponent"]))
    terc = pd.qcut(q.bs_adj, 3, labels=["slowest", "middle", "fastest"])
    A["LVadj_depth_by_speed_tercile"] = {}
    for lab, d in q.groupby(terc, observed=True):
        A["LVadj_depth_by_speed_tercile"][lab] = float(d.LV_adj.corr(d.depth))
        out("      adjusted L/v vs depth, %-7s third (%.1f-%.1f mph, n=%d): %+.2f" % (lab, d.bs_adj.min(), d.bs_adj.max(), len(d), d.LV_adj.corr(d.depth)))
    out("   g) adjusted L/v vs outcomes (partial r)")
    A["LVadj_partials"] = {}
    for o in OUTCOMES:
        r = {"same_ctrl_adj_speed": partial(q, "LV_adj", o, ["bs_adj"]),
             "next_ctrl_adj_speed": partial(p, "LV_adj", o + "_next", ["bs_adj"]),
             "next_ctrl_adj_speed_depth": partial(p, "LV_adj", o + "_next", ["bs_adj", "depth"])}
        A["LVadj_partials"][o] = r
        out("      %-13s same season %+.3f | next season %+.3f | next, also ctrl depth %+.3f" % (o, *r.values()))
    R["hitter_level"] = A
    return q, p


def predictive(p):
    out()
    out("=" * 100)
    out("3. NEXT-SEASON PREDICTION -- out-of-sample R^2 (batter-grouped 10-fold, extras.cv_r2), n=%d pairs" % len(p))
    out("=" * 100)
    specs = {
        "raw speed": ["bs"], "adjusted speed": ["bs_adj"],
        "raw speed + raw L/v": ["bs", "LV"], "raw speed + raw acceleration": ["bs", "acc"],
        "adj speed + adj L/v": ["bs_adj", "LV_adj"], "adj speed + adj acceleration": ["bs_adj", "acc_adj"],
        "adj speed + adj L/v + adj acceleration": ["bs_adj", "LV_adj", "acc_adj"],
        "raw speed + depth": ["bs", "depth"], "raw speed + depth + adj L/v": ["bs", "depth", "LV_adj"],
        "raw speed + depth + adj acceleration": ["bs", "depth", "acc_adj"],
        "adj speed + depth": ["bs_adj", "depth"], "adj speed + depth + adj L/v": ["bs_adj", "depth", "LV_adj"],
        "adj acceleration alone": ["acc_adj"],
    }
    need = sorted({x for xs in specs.values() for x in xs})
    tab = {}
    for name, xs in specs.items():
        tab[name] = {o: cv_r2(p.dropna(subset=need + [o + "_next"]), xs, o + "_next") for o in OUTCOMES}
    T = pd.DataFrame(tab).T[OUTCOMES]
    for line in T.round(4).to_string().splitlines():
        out("   " + line)
    R["cv_r2_next"] = T.round(4).to_dict(orient="index")

    out()
    out("   Is the gain real? R^2 gain x1000, mean of 20 CV splits, 95% CI from resampling batters (* = excludes 0)")
    rng = np.random.default_rng(0)
    A, B, C = ["bs"], ["bs", "depth"], ["bs", "depth", "LV_adj"]
    R["gain_ci"] = {}
    out("   %-13s | %-26s | %-26s | %-26s" % ("outcome", "depth over raw speed", "adj L/v over speed+depth", "both over raw speed"))
    for o in OUTCOMES:
        d = p.dropna(subset=C + [o + "_next"]).reset_index(drop=True)
        yv, bats = d[o + "_next"].to_numpy(), d["batter"].to_numpy()
        se = {"A": sq_err(d, A, o + "_next"), "B": sq_err(d, B, o + "_next"), "C": sq_err(d, C, o + "_next")}
        cells, R["gain_ci"][o] = [], {}
        for a, b, key in (("A", "B", "depth_over_speed"), ("B", "C", "LVadj_over_speed_depth"), ("A", "C", "both_over_speed")):
            pt, lo, hi = boot_gain(se[a], se[b], yv, bats, rng)
            R["gain_ci"][o][key] = (pt, lo, hi)
            cells.append("%+5.1f [%+5.1f, %+5.1f]%s" % (pt, lo, hi, " *" if lo > 0 or hi < 0 else "  "))
        out("   %-13s | %s | %s | %s" % (o, *cells))

    out()
    out("   Page's row 3 (adjusted speed + NEXT season's contact credit) vs raw speed, same test:")
    rng = np.random.default_rng(1)
    R["page_row3_gain_ci"] = {}
    for o in OUTCOMES:
        d = p.dropna(subset=["bs", "bs_adj", "ce_next", o + "_next"]).reset_index(drop=True)
        yv, bats = d[o + "_next"].to_numpy(), d["batter"].to_numpy()
        pt, lo, hi = boot_gain(sq_err(d, ["bs"], o + "_next"), sq_err(d, ["bs_adj", "ce_next"], o + "_next"), yv, bats, rng)
        R["page_row3_gain_ci"][o] = (pt, lo, hi)
        out("   %-13s %+5.1f [%+5.1f, %+5.1f]%s" % (o, pt, lo, hi, "  *" if lo > 0 or hi < 0 else ""))


def elasticity(comp, ref, surfaces):
    out()
    out("=" * 100)
    out("4. DOES SPEED KEEP UP WITH PATH AS CONTACT MOVES OUT FRONT? (constant acceleration predicts elasticity 0.50)")
    out("=" * 100)
    sv, sL = surfaces["bat_speed"], surfaces["swing_length"]
    d = np.arange(0, 61, 1.0)
    v = comp["bat_speed"].mean() + sv.partial("depth", d, ref)
    L = comp["swing_length"].mean() + sL.partial("depth", d, ref)
    dv, dL = np.gradient(v, d), np.gradient(L, d)
    e = (dv / v) / (dL / L)
    out("   CONTROLLED (the page's fitted surfaces: hitter-season FE, count, pitch group, velo). Typical depth %.1f in." % ref["depth"])
    out("   %5s %7s %7s %9s %9s %11s   %s" % ("depth", "speed", "path", "speed%/in", "path%/in", "elasticity", "local accel / avg so far (=2e)"))
    R["elasticity_profile"] = {}
    for x in (5, 10, 15, 20, 25, 30, 35, 40, 42, 45, 50, 55):
        i = int(x)
        R["elasticity_profile"][x] = {"speed": float(v[i]), "path": float(L[i]), "elasticity": float(e[i])}
        out("   %5d %7.1f %7.2f %+9.2f %+9.2f %+11.2f   %+.2f" % (x, v[i], L[i], 100 * dv[i] / v[i], 100 * dL[i] / L[i], e[i], 2 * e[i]))
    R["elasticity_windows_controlled"] = {}
    for lo, hi, lab in ((ref["depth"] - 12, ref["depth"], "12 in behind typical"), (ref["depth"] - 6, ref["depth"] + 6, "+/-6 in around typical"),
                        (ref["depth"], ref["depth"] + 12, "12 in out front of typical")):
        m = (d >= lo) & (d <= hi)
        bv, bL = np.polyfit(d[m], np.log(v[m]), 1)[0], np.polyfit(d[m], np.log(L[m]), 1)[0]
        R["elasticity_windows_controlled"][lab] = float(bv / bL)
        out("   %-28s speed %+.2f%%/in, path %+.2f%%/in, elasticity %.2f" % (lab, 100 * bv, 100 * bL, bv / bL))
    d0 = ref["depth"]
    vv = comp["bat_speed"].mean() + sv.partial("depth", np.array([d0, d0 + 6]), ref)
    LL = comp["swing_length"].mean() + sL.partial("depth", np.array([d0, d0 + 6]), ref)
    acc0, acc6 = vv[0] ** 2 / LL[0], vv[1] ** 2 / LL[1]
    v_const = vv[0] * np.sqrt(LL[1] / LL[0])
    R["worked_example_6in"] = {"speed": [float(vv[0]), float(vv[1])], "path": [float(LL[0]), float(LL[1])],
                               "v2L_change_pct": float(100 * (acc6 / acc0 - 1)), "speed_needed_for_constant_accel": float(v_const)}
    out("   worked example, typical contact -> 6 in further out front: %.1f -> %.1f mph, %.2f -> %.2f ft;"
        % (vv[0], vv[1], LL[0], LL[1]))
    out("      constant acceleration would need %.1f mph; v^2/L changes %+.1f%% instead of 0" % (v_const, 100 * (acc6 / acc0 - 1)))

    out("   UNCONTROLLED (raw within-hitter regression, no pitch/count controls) -- kept for the record; CONFOUNDED:")
    out("   out-front contact over-represents offspeed, where hitters swing softer, so the out-front number is too low")
    cc = comp[["hs", "bat_speed", "swing_length", "depth"]].copy()
    cc["lv"], cc["lL"] = np.log(cc["bat_speed"]), np.log(cc["swing_length"].clip(lower=0.5))
    cc["dc"] = cc["depth"] - cc.groupby("hs")["depth"].transform("mean")
    R["elasticity_windows_uncontrolled"] = {}
    for lo, hi in ((-12, 0), (-6, 6), (0, 12)):
        s = cc[(cc.dc >= lo) & (cc.dc <= hi)].copy()
        for col in ("lv", "lL", "dc"):
            s[col] = s[col] - s.groupby("hs")[col].transform("mean")
        bv, bL = (s.dc * s.lv).sum() / (s.dc ** 2).sum(), (s.dc * s.lL).sum() / (s.dc ** 2).sum()
        R["elasticity_windows_uncontrolled"][f"{lo}..{hi}"] = float(bv / bL)
        out("   own-mean depth %+3d to %+3d in: elasticity %.2f" % (lo, hi, bv / bL))


def ab_swings(comp, sw, outc):
    out()
    out("=" * 100)
    out("5. A-SWING / B-SWING")
    out("=" * 100)
    S = {}
    n_all = sw.groupby("hs").size()
    gap = (sw.groupby("hs")["bat_speed"].median() - sw.groupby("hs")["iqr_floor"].first())[n_all >= 400]
    S["iqr_floor_below_median_mph"] = float(gap.median())
    out("   a) the IQR filter's floor sits %.1f mph below the hitter's median (10th-90th pct %.1f to %.1f) -- a B swing a few mph"
        % (gap.median(), gap.quantile(.1), gap.quantile(.9)))
    out("      slower is nowhere near it, so the filter isn't hiding one")

    def gmm_stats(x):
        x = x.reshape(-1, 1)
        g1 = GaussianMixture(1, random_state=0).fit(x)
        g2 = GaussianMixture(2, n_init=3, random_state=0).fit(x)
        m, s = g2.means_.ravel(), np.sqrt(g2.covariances_.ravel())
        dd = np.sqrt(2) * abs(m[0] - m[1]) / np.sqrt(s[0] ** 2 + s[1] ** 2)
        return g1.bic(x) - g2.bic(x), dd, g2.weights_.min()

    el = comp.groupby("hs").filter(lambda d: len(d) >= 400)
    rows = []
    for hs, d in el.groupby("hs"):
        r = {"hs": hs}
        for col in ("bat_speed", "bat_speed_adj"):
            r[col + "_dbic"], r[col + "_D"], r[col + "_wmin"] = gmm_stats(d[col].to_numpy())
        rows.append(r)
    B = pd.DataFrame(rows)
    out("   b) bimodality, %d hitter-seasons with 400+ competitive swings (clear = BIC prefers 2 by >10, Ashman D > 2, minor mode > 15%%)" % len(B))
    for col in ("bat_speed", "bat_speed_adj"):
        clear = ((B[col + "_dbic"] > 10) & (B[col + "_D"] > 2) & (B[col + "_wmin"] > .15)).mean()
        S[f"bimodal_clear_share_{col}"] = float(clear)
        out("      %-14s BIC prefers 2 components: %3.0f%% | clearly two humps: %4.1f%% | median D %.2f"
            % (col, 100 * (B[col + "_dbic"] > 10).mean(), 100 * clear, B[col + "_D"].median()))
    out("      median within-hitter skew %+.2f (a left tail makes BIC 'prefer' 2 components without two humps)" % el.groupby("hs")["bat_speed"].skew().median())
    rng = np.random.default_rng(11)
    tot = el.groupby("hs")["bat_speed_adj"].std().median()
    out("      power check: planted B swing (35%% of swings, 600 swings), total within-hitter SD held at the observed %.2f mph" % tot)
    S["power"] = {}
    for sep in (2, 3, 4, 5, 6, 7):
        comp_sd = np.sqrt(tot ** 2 - .35 * .65 * sep ** 2)
        hits = 0
        for _ in range(60):
            dbic, dd, w = gmm_stats(rng.normal(72, comp_sd, 600) - sep * (rng.random(600) < .35))
            hits += (dbic > 10) and dd > 2 and w > .15
        S["power"][sep] = hits / 60
        out("        B swing %d mph slower -> detected %3.0f%%" % (sep, 100 * hits / 60))

    # two-strike swing as a per-hitter trait
    c = comp.assign(two=(comp["strikes"] == 2).astype(float))
    grp = pd.get_dummies(c["pitch_group"], drop_first=True, dtype=float).to_numpy()
    X_all = np.column_stack([np.ones(len(c)), c["two"], grp, c["release_speed"].fillna(c["release_speed"].mean())])

    def effects(groups, y, min_each, X=X_all, frame=c):
        yv, rows_ = frame[y].to_numpy(), []
        for key, ix in groups:
            X_, yy = X[ix], yv[ix]
            if X_[:, 1].sum() < min_each or (1 - X_[:, 1]).sum() < min_each:
                continue
            b, *_ = np.linalg.lstsq(X_, yy, rcond=None)
            res = yy - X_ @ b
            cov = np.linalg.pinv(X_.T @ X_) * (res @ res) / (len(yy) - X_.shape[1])
            rows_.append((key, b[1], np.sqrt(cov[1, 1])))
        return tr.shrink(pd.DataFrame(rows_, columns=["hs", "slope", "se"]).set_index("hs"))

    hs_groups = [(hs, ix.to_numpy()) for hs, ix in c.groupby("hs").groups.items() if len(ix) >= MIN_N]
    YS = {"speed_raw": "bat_speed", "speed_same_cp": "bat_speed_adj", "depth_ms": "depth_ms", "length_same_cp": "swing_length_adj"}
    eff = {k: effects(hs_groups, y, 40) for k, y in YS.items()}
    meta = c.groupby("hs")[["batter", "season"]].first()
    out("   c) two-strike vs <2-strike swings, within hitter-season (controls: pitch group, velo), empirical-Bayes shrunk")
    S["two_strike"] = {}
    for k, e in eff.items():
        x = e.join(meta).set_index(["batter", "season"])["slope_shrunk"]
        j = pd.concat([x, x.rename(index=lambda s: s - 1, level="season")], axis=1, join="inner")
        S["two_strike"][k] = {"league_mean": e.attrs["mu"], "tau": e.attrs["tau"], "reliability": float(e["reliability"].mean()),
                              "yoy": float(j.iloc[:, 0].corr(j.iloc[:, 1]))}
        out("      %-15s league %+6.2f | between-hitter SD %.2f | reliability %.2f | yoy %.2f"
            % (k, e.attrs["mu"], e.attrs["tau"], e["reliability"].mean(), S["two_strike"][k]["yoy"]))
    J = pd.concat({k: v["slope_shrunk"] for k, v in eff.items()}, axis=1).dropna()
    S["decomposition"] = {"raw_vs_same_cp": float(J.speed_raw.corr(J.speed_same_cp)), "raw_vs_depth": float(J.speed_raw.corr(J.depth_ms)),
                          "same_cp_vs_depth": float(J.speed_same_cp.corr(J.depth_ms))}
    out("      across hitters: raw drop vs drop at same contact point %+.2f | raw drop vs depth shift %+.2f | the two parts %+.2f"
        % tuple(S["decomposition"].values()))

    # does backing off buy contact? estimate the effect without letting whiffs feed their own predictor
    ok = c["hs"].map(c.groupby("hs").size() >= MIN_N).to_numpy()
    contact = (~c["is_whiff"]).to_numpy()
    grp_c = [(hs, ix.to_numpy()) for hs, ix in c[ok & contact].groupby("hs").groups.items()]
    grp_a = [(hs, ix.to_numpy()) for hs, ix in c[ok].groupby("hs").groups.items()]
    eff_c = pd.DataFrame({k: effects(grp_c, YS[k], 30)["slope_shrunk"] for k in ("speed_same_cp", "depth_ms", "length_same_cp")})
    eff_a = pd.DataFrame({k: effects(grp_a, YS[k], 30)["slope_shrunk"] for k in ("speed_same_cp", "depth_ms")})
    w = c.groupby("hs").apply(lambda d: pd.Series({"whiff2": d.loc[d.two == 1, "is_whiff"].mean(), "whiff01": d.loc[d.two == 0, "is_whiff"].mean(),
                                                   "bs": d["bat_speed"].mean(), "batter": d["batter"].iloc[0], "season": d["season"].iloc[0]}))
    out("   d) payoff: partial r with two-strike whiff rate (controls: <2-strike whiff, bat speed); + = backing off / going deeper -> fewer whiffs")
    h = w.join(eff_c)
    cur = w.join(eff_a).reset_index().set_index(["batter", "season"])
    pp = cur.join(cur[["whiff2", "whiff01", "bs"]].rename(index=lambda s: s - 1, level="season"), rsuffix="_n", how="inner")
    S["whiff_payoff"] = {}
    for k in eff_c:
        S["whiff_payoff"][k] = {"same_season_contact_only": partial(h, k, "whiff2", ["whiff01", "bs"])}
        nxt = ""
        if k in eff_a:
            S["whiff_payoff"][k]["next_season"] = partial(pp, k, "whiff2_n", ["whiff01_n", "bs_n"])
            nxt = " | next season %+.3f" % S["whiff_payoff"][k]["next_season"]
        out("      %-15s same season (effect from contact swings only) %+.3f%s" % (k, S["whiff_payoff"][k]["same_season_contact_only"], nxt))
    h2 = h.join(outc[["ev50", "xwobacon"]])
    S["cost"] = {o: partial(h2, "speed_same_cp", o, ["bs"]) for o in ("ev50", "xwobacon")}
    out("      cost: backing off vs EV50 %+.3f, vs xwOBAcon %+.3f (ctrl bat speed) -- none detectable" % tuple(S["cost"].values()))

    # pooled leaderboard (contact swings, 1,000+ of them)
    cc = c[contact].reset_index(drop=True)
    cc = cc[cc["batter"].map(cc.groupby("batter").size() >= 1000).to_numpy()].reset_index(drop=True)
    grp_p = pd.get_dummies(cc["pitch_group"], drop_first=True, dtype=float).to_numpy()
    Xp = np.column_stack([np.ones(len(cc)), cc["two"], grp_p, cc["release_speed"].fillna(cc["release_speed"].mean())])
    bg = [(b, ix.to_numpy()) for b, ix in cc.groupby("batter").groups.items()]
    lb = pd.DataFrame({"speed": effects(bg, "bat_speed_adj", 0, Xp, cc)["slope_shrunk"],
                       "depth": effects(bg, "depth_ms", 0, Xp, cc)["slope_shrunk"]})
    names = pd.read_csv(HERE / "results" / "depth_cost_by_hitter.csv").drop_duplicates("batter").set_index("batter")["name"]
    lb["name"] = lb.index.map(names)
    lb = lb.dropna(subset=["name"])
    fmt = lambda d, col, u: ", ".join(f"{n} ({x:+.1f}{u})" for n, x in zip(d["name"], d[col]))
    out("   e) leaderboard, 2024-26 pooled, 1,000+ contact swings (n=%d named hitters; median %+.2f mph, %+.2f ms)" % (len(lb), lb.speed.median(), lb.depth.median()))
    out("      backs off most:  " + fmt(lb.nsmallest(8, "speed"), "speed", ""))
    out("      backs off least: " + fmt(lb.nlargest(8, "speed"), "speed", ""))
    out("      goes deepest:    " + fmt(lb.nsmallest(8, "depth"), "depth", " ms"))
    S["leaderboard"] = {"backs_off_most": lb.nsmallest(8, "speed")[["name", "speed"]].values.tolist(),
                        "backs_off_least": lb.nlargest(8, "speed")[["name", "speed"]].values.tolist(),
                        "goes_deepest": lb.nsmallest(8, "depth")[["name", "depth"]].values.tolist()}
    R["ab_swings"] = S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="*", default=DEFAULT_DATA)
    args = ap.parse_args()
    comp, outc, sw, ref, surfaces = build(args.data)
    out("competitive swings: %s (page: 924k)" % f"{len(comp):,}")
    R["competitive_swings"] = len(comp)
    stabilization(comp)
    t = hitter_table(comp, outc)
    q, p = hitter_level(t)
    predictive(p)
    elasticity(comp, ref, surfaces)
    ab_swings(comp, sw, outc)
    res = HERE / "results"
    (res / "followups.json").write_text(json.dumps(R, indent=1, default=lambda o: float(o) if np.isscalar(o) else str(o)), encoding="utf-8")
    (res / "followups_report.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
    print("\nwrote results/followups.json and results/followups_report.txt")


if __name__ == "__main__":
    main()
