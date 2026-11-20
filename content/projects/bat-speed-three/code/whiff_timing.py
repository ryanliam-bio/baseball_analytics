"""whiff_timing.py -- where whiffs happen relative to the hitter's own contact point, by pitch group."""
import numpy as np, pandas as pd
import prep, context as cx
raw = prep.load([f"data/swings_{y}.parquet" for y in (2024, 2025, 2026)])
base, audit = prep.base_filter(raw)
sw = prep.tracked_swings(base, audit)
comp = sw[sw["competitive_iqr"]].reset_index(drop=True)
wh = cx.whiff_anatomy(comp)
wh = wh[wh["pitch_group"].isin(["FB", "BR", "OS"])]
edges = np.arange(-30, 41, 2.0)
rows = []
for g, d in wh.groupby("pitch_group"):
    h, _ = np.histogram(d["depth_dev_ms"].clip(-30, 40), bins=edges)
    rows.append(pd.DataFrame({"pitch_group": g, "left": edges[:-1], "share": h / h.sum()}))
pd.concat(rows).to_csv("results/whiff_timing_hist.csv", index=False)
summ = wh.groupby("pitch_group").agg(whiffs=("depth_dev_ms", "size"), median_dev_ms=("depth_dev_ms", "median"),
                                     share_late=("depth_dev_ms", lambda s: (s < -5).mean()),
                                     share_early=("depth_dev_ms", lambda s: (s > 5).mean()),
                                     median_miss_in=("miss_distance", "median"))
# timing vs path misses: small timing deviation but big miss distance
wh["kind"] = np.where(wh["depth_dev_ms"].abs() > 5, "timing", np.where(wh["miss_distance"] >= 3, "path", "near-miss"))
summ = summ.join(pd.crosstab(wh["pitch_group"], wh["kind"], normalize="index"))
summ.to_csv("results/whiff_timing_summary.csv")
print(summ.round(3).to_string())
print("miss distance by kind:", wh.groupby("kind")["miss_distance"].median().round(2).to_dict())
