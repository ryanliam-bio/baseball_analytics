"""Count mediation using 2.0's (Tango RE288) count buckets, plus depth-cost decomposition."""
import numpy as np, pandas as pd
import prep, contact_model as cm, context as cx, evaluate as ev
raw = prep.load([f"data/swings_{y}.parquet" for y in (2024, 2025, 2026)])
base, audit = prep.base_filter(raw)
sw = prep.tracked_swings(base, audit)
comp = sw[sw.competitive_iqr].reset_index(drop=True)
ref = cm.reference_point(comp)
surf = cm.Surface().fit(comp, "bat_speed")
HIT = {"3-0", "3-1", "2-0", "3-2"}; PIT = {"0-1", "1-2", "0-2", "2-2"}
comp["ct20"] = np.where(comp["count"].isin(HIT), "hitter", np.where(comp["count"].isin(PIT), "pitcher", "neutral"))
grp = cx._dummies(comp["pitch_group"], cm.GROUP_LEVELS); spd = cx.pitch_speed_controls(comp)
m = cx.mediation(comp, "ct20", ["neutral", "hitter", "pitcher"], surf, np.hstack([grp, spd]))
print(m.round(3).to_string())
m.to_csv("results/mediation_count_state_tango.csv")
print("swing share by bucket:", comp.ct20.value_counts(normalize=True).round(3).to_dict())

d = pd.read_csv("results/depth_cost_by_hitter.csv")
d["local"] = d.total_mph_per_ms - d.dev_ms
q = d[d.n >= 400]
print(f"\ndepth cost (400+): var total {q.total_mph_per_ms.var():.5f}, var curve-position part {q.local.var():.5f}, var hitter part {q.dev_ms.var():.5f}, cov*2 {2*q.local.cov(q.dev_ms):.5f}")
print("corr(total, local) =", round(q.total_mph_per_ms.corr(q.local), 2), " corr(total, hitter part) =", round(q.total_mph_per_ms.corr(q.dev_ms), 2))
lb = pd.read_csv("results/depth_cost_leaderboard.csv")
dd = d.groupby("batter").apply(lambda g: pd.Series({"dev_ms": np.average(g.dev_ms, weights=g.n), "local": np.average(g.local, weights=g.n)})).reset_index()
lb = lb.merge(dd, on="batter")
print("\nleaderboard with split (cheapest / steepest 10):")
print(lb.sort_values("mph_per_ms").head(10)[["name", "mph_per_ms", "local", "dev_ms", "depth_ms", "adj_speed"]].round(3).to_string(index=False))
print(lb.sort_values("mph_per_ms").tail(10)[["name", "mph_per_ms", "local", "dev_ms", "depth_ms", "adj_speed"]].round(3).to_string(index=False))
print("league median depth_ms (pooled leaderboard):", round(lb.depth_ms.median(), 1), " n hitters on leaderboard:", len(lb))
