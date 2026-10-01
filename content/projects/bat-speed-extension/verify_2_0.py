"""
verify_2_0.py -- reproduces the Bat Speed Analysis 2.0 corrections from the original data.

    pip install pyreadr pandas numpy
    python verify_2_0.py swings_df_backup.rds

Runs the 2.0 calculations exactly as written (no swing filter) and again with the
IQR filter the page describes (drop swings below Q1 - 1.5*IQR, per batter).
"""
import itertools
import sys

import numpy as np
import pandas as pd
import pyreadr

path = sys.argv[1] if len(sys.argv) > 1 else "swings_df_backup.rds"
df = list(pyreadr.read_r(path).values())[0]
df["game_date"] = pd.to_datetime(df["game_date"])
df["row"] = np.arange(len(df))
df = df.sort_values(["batter", "game_date", "row"], kind="stable")           # arrange(batter, game_date)
q = df.groupby("batter")["bat_speed"].quantile([0.25, 0.75]).unstack()
df = df.join((q[0.25] - 1.5 * (q[0.75] - q[0.25])).rename("iqr_floor"), on="batter")
b, s = df["balls"], df["strikes"]
df["count_type"] = np.where(((b == 3) & (s == 0)) | ((b == 3) & (s == 1)) | ((b == 2) & (s == 0)) | ((b == 3) & (s == 2)), "hitter",
                   np.where(((b == 0) & (s == 1)) | ((b == 1) & (s == 2)) | ((b == 0) & (s == 2)) | ((b == 2) & (s == 2)), "pitcher", "neutral"))
versions = {"as published (no filter)": df, "with IQR filter": df[df["bat_speed"] >= df["iqr_floor"]]}
print(f"{len(df):,} swings; {len(versions['with IQR filter']):,} after the IQR filter\n")


def full_season(d, min_swings):
    n = d.groupby("batter").size()
    return d.groupby("batter")["bat_speed"].mean()[n >= min_swings]


def stabilization(d, grid, full):
    out = {}
    for k in grid:
        early = d.groupby("batter").head(k).groupby("batter")["bat_speed"].mean()
        j = pd.concat([early.rename("early"), full.rename("full")], axis=1, join="inner")
        out[k] = j["early"].corr(j["full"])
    return pd.Series(out)


def first_at(curve, r=0.90):
    hit = curve[curve >= r]
    return int(hit.index[0]) if len(hit) else None


print("1) Stabilization: correlation of first-n-swing average with full-season average (250+ swings)")
grid = list(range(10, 151, 10))
tab = pd.DataFrame({k: stabilization(d, grid, full_season(d, 250)) for k, d in versions.items()}).T
print(tab.round(3).to_string())
print("   first n reaching r = 0.90:", {k: first_at(tab.loc[k]) for k in tab.index}, "\n")

print("2) Stabilization by count type: first n reaching r = 0.90 vs the same count type's full season")
for k, d in versions.items():
    res = {}
    for ct in ("hitter", "neutral", "pitcher"):
        c = d[d["count_type"] == ct]
        res[ct] = first_at(stabilization(c, range(10, 101, 10), full_season(c, 100)))
    junk = (df["bat_speed"] < df["iqr_floor"]).groupby(df["count_type"]).mean().round(3).to_dict()
    print(f"   {k:<26} {res}")
print(f"   share of swings below the IQR floor, by count type: {junk}\n")

print("3) Consistency: r(average bat speed, within-season SD)")
for k, d in versions.items():
    g = d.groupby("batter")["bat_speed"].agg(["mean", "std", "size"])
    a, r = g[g["size"] >= 30], g[g["size"] >= 600]
    print(f"   {k:<26} 30+ swings: {a['mean'].corr(a['std']):+.2f}   600+ swings: {r['mean'].corr(r['std']):+.2f}")
print()

print("4) Bat speed on one pitch type vs another (batters with 30+ swings on both)")
types = ["FF", "SI", "FC", "SL", "CH", "CU"]
for k, d in versions.items():
    g = d[d["pitch_type"].isin(types)].groupby(["batter", "pitch_type"])["bat_speed"].agg(["mean", "size"]).reset_index()
    w = g[g["size"] >= 30].pivot(index="batter", columns="pitch_type", values="mean")
    rs = [w[a].corr(w[c]) for a, c in itertools.combinations(types, 2)]
    print(f"   {k:<26} r ranges {min(rs):.2f} to {max(rs):.2f} across all {len(rs)} pairs")
print()

print("5) Average bat speed, changeups vs four-seamers")
for k, d in versions.items():
    m = d.groupby("pitch_type")["bat_speed"].mean()
    print(f"   {k:<26} CH {m['CH']:.1f}   FF {m['FF']:.1f}")
