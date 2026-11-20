"""
run_all.py -- Bat Speed 3.0 pipeline.

    python run_all.py --data swings_2024.parquet swings_2025.parquet swings_2026.parquet
    python run_all.py --simulate            # pipeline test on synthetic swings with known truths

Writes everything to ./results (CSV + summary.json).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import contact_model as cm
import context as cx
import evaluate as ev
import prep
import tradeoff as tr

OUTCOMES = ["barrel_rate", "ev50", "hardhit_rate", "xwobacon", "whiff_rate"]
KING_METRICS = ["bat_speed", "bat_speed_adj", "bat_speed_adjfull", "bat_speed_p90", "bat_speed_adj_p90",
                "swing_length", "swing_length_adj", "impulse", "impulse_adj",
                "length_per_mph", "length_per_mph_adj", "depth", "depth_ms", "contact_effect"]
MIN_N = 150          # competitive tracked swings for a hitter-season to enter correlation tables


def log(msg, t0=[time.time()]):
    print(f"[{time.time() - t0[0]:6.1f}s] {msg}", flush=True)


def jsonable(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, pd.DataFrame):
        return o.round(4).reset_index().to_dict("records")
    if isinstance(o, pd.Series):
        return {str(k): jsonable(v) for k, v in o.round(4).items()}
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="*")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--out", default="results")
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    S: dict = {}

    # ---------------------------------------------------------------- load + prep
    if args.simulate:
        from simulate import simulate, TRUTH
        data, pool = simulate()
        raw = pd.concat(data.values(), ignore_index=True)
        S["truth"] = TRUTH
    else:
        raw = prep.load(args.data)
    log(f"loaded {len(raw):,} rows")
    S["bunts_flagged_by_season"] = raw.groupby("game_year")["is_bunt"].sum().to_dict()

    base, audit = prep.base_filter(raw)
    del raw
    S["data_quality"] = prep.data_quality(base)
    outc = prep.outcomes(base)
    sw = prep.tracked_swings(base, audit)
    S["audit"] = audit
    comp = sw[sw["competitive_iqr"]].reset_index(drop=True)
    S["audit"]["competitive_swings"] = len(comp)
    S["iqr_removed_depth"] = {"removed_mean_depth": float(sw.loc[~sw.competitive_iqr, "depth"].mean()),
                              "kept_mean_depth": float(comp["depth"].mean())}
    log(f"competitive swings: {len(comp):,}")

    # ---------------------------------------------------------------- contact surface
    ref = cm.reference_point(comp)
    S["reference_point"] = ref
    S["variance_decomposition"] = {y: cm.variance_decomposition(comp, y) for y in ("bat_speed", "swing_length")}

    fits = {}
    for y in ("bat_speed", "swing_length"):
        fits[y] = {
            "inches_full": cm.oos_within_r2(comp, y, lambda: cm.Surface()),
            "ms_full": cm.oos_within_r2(comp, y, lambda: cm.Surface(depth_var="depth_ms")),
            "inches_additive": cm.oos_within_r2(comp, y, lambda: cm.Surface(interactions=False)),
            "depth_only": cm.oos_within_r2(comp, y, lambda: cm.Surface(main_vars=("depth",))),
        }
        log(f"oos within R2 {y}: " + ", ".join(f"{k}={v:.3f}" for k, v in fits[y].items()))
    S["oos_within_r2"] = fits

    within = cm.Surface().fit(comp, "bat_speed")
    pooled = cm.Surface().fit(comp, "bat_speed", groups=None)
    within_ms = cm.Surface(depth_var="depth_ms").fit(comp, "bat_speed")
    grids = {"depth": np.arange(0, 61, 2.0), "offbody": np.arange(22, 55, 1.0), "height": np.arange(-0.2, 1.25, 0.05)}
    curves = []
    for var, grid in grids.items():
        for label, s in (("within", within), ("pooled", pooled)):
            curves.append(pd.DataFrame({"var": var, "x": grid, "model": label, "mph": s.partial(var, grid, ref)}))
    ms_grid = np.arange(0, 45, 1.0)
    curves.append(pd.DataFrame({"var": "depth_ms", "x": ms_grid, "model": "within",
                                "mph": within_ms.partial("depth", ms_grid, ref)}))
    curves = pd.concat(curves)
    curves.to_csv(out / "contact_curves.csv", index=False)
    slope = lambda s, v, at: (s.partial(v, np.array([at + 1.0]), ref)[0] - s.partial(v, np.array([at - 1.0]), ref)[0]) / 2
    S["depth_slope_at_ref_mph_per_in"] = {"within": slope(within, "depth", ref["depth"]),
                                          "pooled": slope(pooled, "depth", ref["depth"])}
    S["depth_slope_at_ref_mph_per_ms"] = slope(within_ms, "depth", ref["depth_ms"])
    S["context_effects_in_surface"] = within.context_effects()

    # per-season surfaces (stability of the adjustment itself)
    S["depth_slope_by_season"] = {}
    for s_ in sorted(comp["season"].unique()):
        sub = comp[comp["season"] == s_]
        S["depth_slope_by_season"][int(s_)] = slope(cm.Surface().fit(sub, "bat_speed"), "depth", ref["depth"])

    # ---------------------------------------------------------------- adjusted metrics + hitter table
    comp, surfaces = ev.add_adjusted_columns(comp, ref)
    tab = ev.hitter_table(comp, outc)
    tab.to_csv(out / "hitter_seasons.csv")
    log(f"hitter-season table: {len(tab):,} rows, {int((tab.n >= MIN_N).sum())} with >= {MIN_N} swings")
    q = tab[tab["n"] >= MIN_N]
    S["raw_vs_adj_corr"] = {"bat_speed": q["bat_speed"].corr(q["bat_speed_adj"]),
                            "swing_length": q["swing_length"].corr(q["swing_length_adj"]),
                            "impulse": q["impulse"].corr(q["impulse_adj"])}
    S["contact_effect_spread_mph"] = q["contact_effect"].describe(percentiles=[.05, .5, .95]).to_dict()

    # ---------------------------------------------------------------- reliability
    rel_metrics = ["bat_speed", "bat_speed_adj", "bat_speed_adjfull", "swing_length", "swing_length_adj",
                   "impulse", "impulse_adj", "depth", "depth_ms"]
    stab = ev.stabilization(comp, rel_metrics)
    stab.to_csv(out / "stabilization.csv", index=False)
    S["swings_to_r90_full"] = ev.swings_to_threshold(stab, "r_full", 0.9)
    S["swings_to_r80_rest"] = ev.swings_to_threshold(stab, "r_rest", 0.8)
    S["split_half"] = ev.split_half(comp, rel_metrics)
    yoy = ev.year_over_year(tab, KING_METRICS + OUTCOMES, min_n=200)
    yoy.to_csv(out / "year_over_year.csv", index=False)
    S["yoy"] = yoy.groupby("metric")["r"].mean().sort_values(ascending=False)
    log("reliability done")

    # ---------------------------------------------------------------- validity (the king table)
    same = ev.corr_table(q.reset_index(), KING_METRICS, OUTCOMES)
    pairs = ev.paired_seasons(tab, MIN_N)
    nxt = ev.corr_table(pairs, KING_METRICS, OUTCOMES, suffix="_next")
    same.to_csv(out / "king_table_same_season.csv")
    nxt.to_csv(out / "king_table_next_season.csv")
    S["king_same"], S["king_next"] = same, nxt
    diffs = []
    for contrast in (("bat_speed", "bat_speed_adj"), ("bat_speed", "bat_speed_adjfull"),
                     ("swing_length", "swing_length_adj"), ("impulse", "impulse_adj")):
        for o in OUTCOMES:
            for label, d, oc in (("same", q.reset_index(), o), ("next", pairs, o + "_next")):
                p, lo, hi = ev.bootstrap_diff(d, contrast[0], contrast[1], oc, n_boot=args.boot)
                diffs.append({"raw": contrast[0], "adjusted": contrast[1], "outcome": o, "window": label,
                              "r_diff": p, "ci_lo": lo, "ci_hi": hi})
    diffs = pd.DataFrame(diffs)
    diffs.to_csv(out / "adjusted_minus_raw_bootstrap.csv", index=False)
    S["adjusted_minus_raw"] = diffs
    S["incremental_next_season"] = {
        o: ev.incremental_r2(pairs, ["bat_speed"], ["bat_speed_adj", "depth"], o + "_next") for o in OUTCOMES}
    log("validity done")

    # ---------------------------------------------------------------- tradeoff (cost of letting it travel)
    res_in = tr.residuals(comp, surfaces["bat_speed"])
    sl_in = tr.hitter_slopes(comp, res_in, "depth")
    res_ms = tr.residuals(comp, within_ms)
    sl_ms = tr.hitter_slopes(comp, res_ms, "depth_ms")
    local_in = tr.league_local_slope(surfaces["bat_speed"], ref, sl_in["mean_x"].to_numpy())
    local_ms = tr.league_local_slope(within_ms, ref, sl_ms["mean_x"].to_numpy())
    sl = pd.DataFrame({
        "n": sl_in["n"], "mean_depth": sl_in["mean_x"],
        "dev_in": sl_in["slope_shrunk"], "total_mph_per_in": local_in + sl_in["slope_shrunk"],
        "dev_ms": sl_ms["slope_shrunk"], "total_mph_per_ms": local_ms + sl_ms["slope_shrunk"],
        "rel_in": sl_in["reliability"],
    }).join(tab[["season", "batter", "name", "bat_speed", "bat_speed_adj", "depth_ms"] + OUTCOMES])
    sl.to_csv(out / "depth_cost_by_hitter.csv")
    S["tradeoff"] = {
        "tau_mph_per_in": sl_in.attrs["tau"], "tau_mph_per_ms": sl_ms.attrs["tau"],
        "mean_reliability_in": float(sl_in["reliability"].mean()),
        "split_half_in": tr.split_half_slopes(comp, res_in, "depth"),
        "split_half_ms": tr.split_half_slopes(comp, res_ms, "depth_ms"),
        "yoy_dev_in": ev.year_over_year(sl.assign(n=sl["n"]), ["dev_in", "dev_ms"], min_n=300)
                        .groupby("metric")["r"].mean().to_dict(),
        "corr_with": {o: sl["total_mph_per_ms"].corr(sl[o]) for o in OUTCOMES + ["bat_speed", "depth_ms"]},
        "dist_total_mph_per_ms": sl["total_mph_per_ms"].describe(percentiles=[.1, .5, .9]).to_dict(),
    }
    if args.simulate:
        truth = pool.set_index("batter")
        est = sl.join(truth[["slope_true"]], on="batter")
        true_local = est["slope_true"] + 2 * TRUTH["curvature"] * (est["mean_depth"] - TRUTH["depth_ref"])
        S["tradeoff"]["sim_recovery"] = {"corr_est_true": est["total_mph_per_in"].corr(true_local),
                                         "mean_est": float(est["total_mph_per_in"].mean()),
                                         "mean_true": float(true_local.mean())}
        tt = tab.join(truth[["speed_true"]], on="batter")
        tt = tt[tt["n"] >= MIN_N]
        S["sim_speed_recovery"] = {m: tt[m].corr(tt["speed_true"]) for m in ("bat_speed", "bat_speed_adj", "bat_speed_adjfull")}
    log("tradeoff done")

    # ---------------------------------------------------------------- context mediation
    grp_d = cx._dummies(comp["pitch_group"], cm.GROUP_LEVELS)
    cnt_d = cx._dummies(comp["count"], cm.COUNT_LEVELS)
    spd = cx.pitch_speed_controls(comp)
    med_count = cx.mediation(comp, "count", cm.COUNT_LEVELS, surfaces["bat_speed"], np.hstack([grp_d, spd]))
    med_state = cx.mediation(comp, "count_state", ["neutral", "hitter", "pitcher"], surfaces["bat_speed"],
                             np.hstack([grp_d, spd]))
    med_group = cx.mediation(comp, "pitch_group", cm.GROUP_LEVELS, surfaces["bat_speed"], np.hstack([cnt_d, spd]))
    types_present = [t for t in cx.MAIN_TYPES if (comp["pitch_type"].astype(str) == t).sum() > 2000]
    by_type = cx.raw_vs_adjusted_by(comp.assign(pitch_type=comp["pitch_type"].astype(str)), "pitch_type", types_present)
    for name, d in (("mediation_count", med_count), ("mediation_count_state", med_state),
                    ("mediation_pitch_group", med_group), ("bat_speed_by_pitch_type", by_type)):
        d.to_csv(out / f"{name}.csv")
        S[name] = d
    log("context done")

    # ---------------------------------------------------------------- timing + whiffs
    ts = cx.timing_shift(comp)
    ts = ts.join(tab[["n", "whiff_rate", "season", "batter"]])
    S["timing_shift"] = {
        "summary": ts[["shift_BR_ms", "shift_OS_ms"]].describe().to_dict(),
        "split_half_note": "see timing_shift.csv",
        "corr_whiff": {c: ts[c].corr(ts["whiff_rate"]) for c in ("shift_BR_ms", "shift_OS_ms")},
    }
    ts.to_csv(out / "timing_shift.csv")
    wh = cx.whiff_anatomy(comp)
    if "miss_distance" in wh:
        S["whiff_anatomy"] = {
            "n_whiffs": len(wh),
            "depth_dev_ms": wh["depth_dev_ms"].describe(percentiles=[.1, .25, .5, .75, .9]).to_dict(),
            "by_group_dev_ms": wh.groupby("pitch_group")["depth_dev_ms"].median().to_dict(),
            "miss_vs_absdev_corr": wh["miss_distance"].corr(wh["depth_dev_ms"].abs()),
        }
    log("timing done")

    # ---------------------------------------------------------------- robustness
    rob = {}
    alt = sw[sw["competitive_50"]].reset_index(drop=True)
    alt, _ = ev.add_adjusted_columns(alt, ref, outcomes=("bat_speed",))
    ta = alt.groupby("hs")[["bat_speed", "bat_speed_adj"]].mean().join(tab["n"], how="inner")
    ta = ta[ta["n"] >= MIN_N]
    rob["adj_speed_iqr_vs_50mph_filter_r"] = ta["bat_speed_adj"].corr(tab.loc[ta.index, "bat_speed_adj"])
    s_add = cm.Surface(interactions=False).fit(comp, "bat_speed")
    adj_add = pd.Series(cm.adjust(comp, "bat_speed", s_add), index=comp.index).groupby(comp["hs"]).mean()
    rob["adj_speed_additive_vs_full_r"] = adj_add.loc[q.index].corr(q["bat_speed_adj"])
    s_pool = cm.Surface().fit(comp, "bat_speed", groups=None)
    adj_pool = pd.Series(cm.adjust(comp, "bat_speed", s_pool), index=comp.index).groupby(comp["hs"]).mean()
    rob["adj_speed_pooled_vs_within_r"] = adj_pool.loc[q.index].corr(q["bat_speed_adj"])
    S["robustness"] = rob
    log("robustness done")

    (out / "summary.json").write_text(json.dumps(jsonable(S), indent=1, default=str))
    log(f"wrote {out}/summary.json")


if __name__ == "__main__":
    main()
