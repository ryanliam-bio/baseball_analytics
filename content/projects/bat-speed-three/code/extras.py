"""
extras.py -- follow-ups prompted by the first real-data run.

1. Timing shift recomputed on contact swings only (fouls + balls in play), so a
   hitter's whiffs can't manufacture his own "out front on spin" number.
2. Two-axis profile: does (engine = adjusted speed) + (where he meets it = depth)
   beat raw bat speed at predicting next season?
3. Why raw bat speed out-predicts adjusted: how contact effect relates to the rest.
4. Depth-cost leaderboard and the hitter-specific part of it.
5. Finer stabilization grid (3-30 swings).
6. Untracked hard-hit balls per hitter.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import contact_model as cm
import evaluate as ev
import prep

DATA = [f"data/swings_{y}.parquet" for y in (2024, 2025, 2026)]
OUT = Path("results")
OUTCOMES = ["barrel_rate", "ev50", "hardhit_rate", "xwobacon", "whiff_rate"]


def ols_r2(d: pd.DataFrame, xs: list[str], y: str) -> float:
    X = np.column_stack([np.ones(len(d))] + [d[c] for c in xs])
    b = np.linalg.lstsq(X, d[y], rcond=None)[0]
    return 1 - (d[y] - X @ b).var() / d[y].var()


def cv_r2(d: pd.DataFrame, xs: list[str], y: str, k: int = 10, seed: int = 3) -> float:
    """Out-of-sample R^2, folds split by batter."""
    rng = np.random.default_rng(seed)
    bat = d["batter"].unique()
    f = d["batter"].map(dict(zip(bat, rng.integers(0, k, len(bat))))).to_numpy()
    pred = np.empty(len(d))
    for i in range(k):
        tr, te = d[f != i], d[f == i]
        X = np.column_stack([np.ones(len(tr))] + [tr[c] for c in xs])
        b = np.linalg.lstsq(X, tr[y], rcond=None)[0]
        pred[f == i] = np.column_stack([np.ones(len(te))] + [te[c] for c in xs]) @ b
    return 1 - ((d[y] - pred) ** 2).mean() / d[y].var()


def main():
    R = {}
    raw = prep.load(DATA)
    base, audit = prep.base_filter(raw)
    outc = prep.outcomes(base)

    # 6. untracked hard-hit balls
    bbe = base[base["is_bbe"]].assign(untracked=lambda d: d["bat_speed"].isna())
    u = bbe.groupby("hs").agg(untracked_share=("untracked", "mean"), bbe=("untracked", "size"))
    u = u[u["bbe"] >= 150].join(outc[["ev50"]])
    R["untracked_bbe"] = {
        "corr_untracked_share_ev50": u["untracked_share"].corr(u["ev50"]),
        "ev_ge_105_untracked_share": float(bbe.loc[bbe["launch_speed"] >= 105, "untracked"].mean()),
        "ev_lt_90_untracked_share": float(bbe.loc[bbe["launch_speed"] < 90, "untracked"].mean()),
    }

    sw = prep.tracked_swings(base, audit)
    comp = sw[sw["competitive_iqr"]].reset_index(drop=True)
    ref = cm.reference_point(comp)
    comp, surfaces = ev.add_adjusted_columns(comp, ref, outcomes=("bat_speed",))
    tab = pd.read_csv(OUT / "hitter_seasons.csv", index_col="hs")

    # 1. timing shift on contact swings only
    contact = comp[~comp["is_whiff"]]
    p = contact.pivot_table(index="hs", columns="pitch_group", values="depth_ms", aggfunc=["mean", "size"])
    ts = pd.DataFrame(index=p.index)
    for grp in ("BR", "OS"):
        ok = (p[("size", grp)] >= 40) & (p[("size", "FB")] >= 40)
        ts[f"shift_{grp}"] = (p[("mean", grp)] - p[("mean", "FB")]).where(ok)
    ts["shift_spin"] = ts[["shift_BR", "shift_OS"]].mean(axis=1, skipna=False)
    # split-half reliability (odd/even contact swings)
    c2 = contact.assign(half=contact.groupby("hs").cumcount() % 2)
    halves = []
    for h in (0, 1):
        q = c2[c2["half"] == h].pivot_table(index="hs", columns="pitch_group", values="depth_ms", aggfunc="mean")
        halves.append(q["BR"] - q["FB"])
    both = halves[0].dropna().index.intersection(halves[1].dropna().index)
    both = both.intersection(ts["shift_BR"].dropna().index)
    r = halves[0].loc[both].corr(halves[1].loc[both])
    tab = tab.join(ts)
    q = tab[tab["n"] >= 150]
    R["timing_shift_contact_only"] = {
        "shift_BR_ms_mean": float(ts["shift_BR"].mean()), "shift_BR_ms_sd": float(ts["shift_BR"].std()),
        "shift_OS_ms_mean": float(ts["shift_OS"].mean()), "shift_OS_ms_sd": float(ts["shift_OS"].std()),
        "split_half_BR": 2 * r / (1 + r),
        "corr_same_season": {o: q["shift_spin"].corr(q[o]) for o in OUTCOMES + ["bat_speed", "depth_ms"]},
    }
    yoy = ev.year_over_year(tab, ["shift_BR", "shift_OS", "shift_spin"], min_n=200)
    R["timing_shift_contact_only"]["yoy"] = yoy.groupby("metric")["r"].mean().to_dict()

    # 2. profile model comparison for next season (and same season)
    pairs = ev.paired_seasons(tab, 150)
    specs = {
        "raw speed": ["bat_speed"],
        "adjusted speed": ["bat_speed_adj"],
        "adjusted speed + depth": ["bat_speed_adj", "depth_ms"],
        "raw speed + depth": ["bat_speed", "depth_ms"],
        "raw speed + depth + spin shift": ["bat_speed", "depth_ms", "shift_spin"],
        "adj speed + depth + spin shift": ["bat_speed_adj", "depth_ms", "shift_spin"],
    }
    rows = []
    for o in OUTCOMES:
        d = pairs.dropna(subset=["bat_speed", "bat_speed_adj", "depth_ms", "shift_spin", o + "_next"])
        for name, xs in specs.items():
            rows.append({"outcome": o, "model": name, "cv_r2_next": cv_r2(d, xs, o + "_next"), "n": len(d)})
    prof = pd.DataFrame(rows).pivot(index="model", columns="outcome", values="cv_r2_next").loc[list(specs)]
    prof.to_csv(OUT / "profile_models_next_season.csv")
    R["profile_models_next_season_cv_r2"] = prof.round(4).to_dict()
    # standardized coefficients for whiff next season
    d = pairs.dropna(subset=["bat_speed_adj", "depth_ms", "shift_spin", "whiff_rate_next"]).copy()
    z = lambda s: (s - s.mean()) / s.std()
    X = np.column_stack([np.ones(len(d)), z(d["bat_speed_adj"]), z(d["depth_ms"]), z(d["shift_spin"])])
    b = np.linalg.lstsq(X, z(d["whiff_rate_next"]), rcond=None)[0]
    R["whiff_next_std_betas"] = {"adj_speed": b[1], "depth_ms": b[2], "spin_shift": b[3], "n": len(d)}
    for o in ("ev50", "barrel_rate", "xwobacon"):
        b = np.linalg.lstsq(X, z(d[o + "_next"]), rcond=None)[0]
        R[f"{o}_next_std_betas"] = {"adj_speed": b[1], "depth_ms": b[2], "spin_shift": b[3]}

    # 3. why raw > adjusted
    R["why_raw_wins"] = {
        "corr_contact_effect_adj_speed": q["contact_effect"].corr(q["bat_speed_adj"]),
        "corr_contact_effect_depth_ms": q["contact_effect"].corr(q["depth_ms"]),
        "corr_depth_ms_adj_speed": q["depth_ms"].corr(q["bat_speed_adj"]),
        "sd_raw": q["bat_speed"].std(), "sd_adj": q["bat_speed_adj"].std(), "sd_contact_effect": q["contact_effect"].std(),
    }

    # 4. depth cost: hitter-specific part
    dc = pd.read_csv(OUT / "depth_cost_by_hitter.csv", index_col="hs")
    dcq = dc[dc["n"] >= 400]
    R["depth_cost"] = {
        "corr_dev_ms_with": {o: dcq["dev_ms"].corr(dcq[o]) for o in OUTCOMES + ["bat_speed_adj", "depth_ms"]},
        "corr_total_ms_with_depth_ms": dcq["total_mph_per_ms"].corr(dcq["depth_ms"]),
        "n": len(dcq),
    }
    pool_dc = (dc[dc["n"] >= 300].groupby(["batter", "name"])
               .apply(lambda g: pd.Series({"seasons": len(g), "swings": g["n"].sum(),
                                           "mph_per_ms": np.average(g["total_mph_per_ms"], weights=g["n"]),
                                           "depth_ms": np.average(g["depth_ms"], weights=g["n"]),
                                           "adj_speed": np.average(g["bat_speed_adj"], weights=g["n"])}))
               .reset_index())
    pool_dc = pool_dc[pool_dc["swings"] >= 1000].sort_values("mph_per_ms")
    pool_dc.to_csv(OUT / "depth_cost_leaderboard.csv", index=False)
    R["depth_cost_leaders_cheapest"] = pool_dc.head(10).round(3).to_dict("records")
    R["depth_cost_leaders_steepest"] = pool_dc.tail(10).round(3).to_dict("records")

    # 5. finer stabilization
    stab = ev.stabilization(comp, ["bat_speed", "bat_speed_adj"], grid=(2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50))
    stab.to_csv(OUT / "stabilization_fine.csv", index=False)
    R["fine_swings_to_r90_full"] = ev.swings_to_threshold(stab, "r_full", 0.9)
    R["fine_swings_to_r80_rest"] = ev.swings_to_threshold(stab, "r_rest", 0.8)
    R["fine_swings_to_r70_rest"] = ev.swings_to_threshold(stab, "r_rest", 0.7)

    # swing length fine stabilization (needs its own surface)
    comp2, _ = ev.add_adjusted_columns(comp, ref, outcomes=("swing_length", "impulse"))
    stab2 = ev.stabilization(comp2, ["swing_length", "swing_length_adj", "impulse", "impulse_adj"],
                             grid=(2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50))
    stab2.to_csv(OUT / "stabilization_fine_length.csv", index=False)
    R["fine_swings_to_r90_full"].update(ev.swings_to_threshold(stab2, "r_full", 0.9))
    R["fine_swings_to_r80_rest"].update(ev.swings_to_threshold(stab2, "r_rest", 0.8))

    # leaderboards: 2026 raw vs adjusted
    t26 = tab[(tab["season"] == 2026) & (tab["n"] >= 400)].copy()
    t26["raw_rank"] = t26["bat_speed"].rank(ascending=False).astype(int)
    t26["adj_rank"] = t26["bat_speed_adj"].rank(ascending=False).astype(int)
    t26[["name", "n", "bat_speed", "bat_speed_adj", "contact_effect", "depth_ms", "raw_rank", "adj_rank"]] \
        .sort_values("contact_effect").to_csv(OUT / "leaderboard_2026_contact_effect.csv")
    R["n_qualified_2026"] = len(t26)

    (OUT / "extras.json").write_text(json.dumps(R, indent=1, default=float))
    print(json.dumps(R, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
