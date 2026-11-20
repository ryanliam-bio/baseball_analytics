"""verify.py -- independent re-derivation of headline numbers with separate, simpler code."""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

d = pd.concat([pd.read_parquet(f"data/swings_{y}.parquet") for y in (2024, 2025, 2026)], ignore_index=True)
d = d[(d.game_type.astype(str) == "R") & ~d.is_bunt]
d = d.dropna(subset=["bat_speed", "swing_length", "intercept_ball_minus_batter_pos_y_inches",
                     "intercept_ball_minus_batter_pos_x_inches", "plate_z", "sz_top", "sz_bot"])
d["key"] = d.game_year.astype(str) + "_" + d.batter.astype(str)
# fresh IQR filter
q = d.groupby("key").bat_speed.quantile([.25, .75]).unstack()
lo = (q[0.25] - 1.5 * (q[0.75] - q[0.25])).rename("lo")
d = d.join(lo, on="key")
d = d[d.bat_speed >= d.lo].copy()
print("competitive swings", len(d))
d["dep"] = d["intercept_ball_minus_batter_pos_y_inches"]
d["off"] = d["intercept_ball_minus_batter_pos_x_inches"]
d["hz"] = (d.plate_z - d.sz_bot) / (d.sz_top - d.sz_bot)
for c in ["bat_speed", "swing_length", "dep", "off", "hz"]:
    d[c + "_w"] = d[c] - d.groupby("key")[c].transform("mean")

# (a) within-hitter depth slope, local linear fit in +-6 in around the median depth
med = d.dep.median()
band = d[(d.dep - med).abs() <= 6]
b = np.polyfit(band.dep_w, band.bat_speed_w, 1)[0]
print(f"(a) within-hitter mph/in near median depth ({med:.1f} in): {b:.3f}   [pipeline: 0.219]")
bins = pd.cut(d.dep, [-12, 5, 15, 25, 35, 45, 55, 72])
print("    within-hitter bat speed by depth bin (mph vs hitter mean):",
      d.groupby(bins, observed=True).bat_speed_w.mean().round(2).to_dict())

# (b) pitch type raw means
pt = d.groupby(d.pitch_type.astype(str)).bat_speed.agg(["mean", "size"])
print("(b) raw bat speed CH vs FF:", round(pt.loc["CH", "mean"], 2), round(pt.loc["FF", "mean"], 2),
      "[pipeline: 71.81 vs 70.83]")

# (c) count state within-hitter totals (no controls)
cnt = d.balls.astype(int).astype(str) + "-" + d.strikes.astype(int).astype(str)
state = np.where(cnt.isin(["1-0", "2-0", "3-0", "2-1", "3-1"]), "hitter",
                 np.where(cnt.isin(["0-1", "0-2", "1-2", "2-2"]), "pitcher", "neutral"))
m = d.groupby(state)[["bat_speed_w", "dep_w"]].mean()
print("(c) within-hitter pitcher-count minus neutral: speed", round(m.loc["pitcher", "bat_speed_w"] - m.loc["neutral", "bat_speed_w"], 2),
      " depth", round(m.loc["pitcher", "dep_w"] - m.loc["neutral", "dep_w"], 2), "[pipeline w/ pitch controls: -1.56 mph, -1.80 in]")

# (d) contact point share of within-hitter swing length / bat speed variance, gradient boosting, batter-grouped folds
rng = np.random.default_rng(11)
bat = d.batter.unique(); fold = d.batter.map(dict(zip(bat, rng.integers(0, 3, len(bat))))).to_numpy()
X = d[["dep", "off", "hz"]].to_numpy()
for y in ("swing_length_w", "bat_speed_w"):
    pred = np.empty(len(d))
    for k in range(3):
        tr = fold != k
        m_ = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.1).fit(X[tr], d[y].to_numpy()[tr])
        pred[~tr] = m_.predict(X[~tr])
    # re-demean predictions within hitter-season before scoring
    p = pd.Series(pred, index=d.index); p = p - p.groupby(d.key).transform("mean")
    r2 = 1 - ((d[y] - p) ** 2).sum() / (d[y] ** 2).sum()
    print(f"(d) GBM out-of-sample within-hitter R2 for {y}: {r2:.3f}   [pipeline spline: {'0.858' if 'length' in y else '0.275'}]")

# (e) next-season correlations from the hitter table, separate merge
t = pd.read_csv("results/hitter_seasons.csv")
t = t[t.n >= 150]
a = t[["batter", "season", "bat_speed", "bat_speed_adj", "swing_length", "swing_length_adj"]]
b_ = t[["batter", "season", "whiff_rate", "ev50", "barrel_rate"]].assign(season=lambda x: x.season - 1)
j = a.merge(b_, on=["batter", "season"])
print("(e) next-season r, n =", len(j))
for o in ("ev50", "barrel_rate", "whiff_rate"):
    print("    ", o, {m_: round(j[m_].corr(j[o]), 3) for m_ in ("bat_speed", "bat_speed_adj", "swing_length", "swing_length_adj")})
print("    hitter-level corr(swing_length_adj, bat_speed_adj) =", round(t.swing_length_adj.corr(t.bat_speed_adj), 3),
      "  corr(swing_length, bat_speed) =", round(t.swing_length.corr(t.bat_speed), 3))
