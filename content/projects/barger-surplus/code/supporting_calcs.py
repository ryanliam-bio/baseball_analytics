"""Rebuilds the scouting numbers in the Barger write-up from public Baseball Savant endpoints.
Run: python supporting_calcs.py  (needs pandas; downloads about 10 CSVs, about a minute)

Percentiles use rank / n with the hitter included, the same way Robert Orr's app displays them.
Unless noted, the pool is 2025 MLB regular season, 300+ PA.
"""
import io
import urllib.request

import pandas as pd

ID = 680718  # Addison Barger
SAVANT = "https://baseballsavant.mlb.com"


def savant_csv(path):
    req = urllib.request.Request(SAVANT + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return pd.read_csv(io.StringIO(r.read().decode("utf-8-sig")))


def pctile(s, mask):
    """Percentile of the flagged row within series s (rank / n, hitter included)."""
    return s.rank(pct=True)[mask].iloc[0] * 100


def custom(year):
    sel = "pa,xwoba,hard_hit_percent,oz_swing_percent,whiff_percent,avg_swing_speed,squared_up_swing"
    d = savant_csv(f"/leaderboard/custom?year={year}&type=batter&filter=&min=150&selections={sel}"
                   "&chart=false&x=pa&y=pa&r=no&chartType=beeswarm&sort=xwoba&sortDir=desc&csv=true")
    return d.rename(columns={d.columns[0]: "name"})


# 1. Contact point and bat speed: Swing Path / Attack Angle leaderboard, 300+ competitive swings
print("== Contact point (avg_intercept_y_vs_batter, + = further out front) and bat speed, 300+ swings")
for yr in (2024, 2025):
    d = savant_csv(f"/leaderboard/bat-tracking/swing-path-attack-angle?gameType=Regular&minSwings=300"
                   f"&minGroupSwings=1&seasonStart={yr}&seasonEnd={yr}&type=batter&csv=true")
    d["avg_bat_speed"] = pd.to_numeric(d.avg_bat_speed)
    me = d.id == ID
    b = d[me].iloc[0]
    print(f"   {yr}: depth {b.avg_intercept_y_vs_batter:.1f} in ({pctile(d.avg_intercept_y_vs_batter, me):.0f}th pct of {len(d)}), "
          f"bat speed {b.avg_bat_speed:.1f} mph ({pctile(d.avg_bat_speed, me):.0f}th pct)")

# 2. Hard-hit rate (EV 95+), custom leaderboard
c24, c25 = custom(2024), custom(2025)
print(f"\n== Hard-hit rate: 2024 {c24[c24.player_id == ID].hard_hit_percent.iloc[0]:.1f}% "
      f"-> 2025 {c25[c25.player_id == ID].hard_hit_percent.iloc[0]:.1f}%")

# 3. Chase and whiff vs. the 300+ PA pool (higher = worse for both)
q = c25[c25.pa >= 300].copy()
b = q[q.player_id == ID].iloc[0]
print(f"\n== 2025, 300+ PA (n={len(q)}): chase {b.oz_swing_percent:.1f}% (median {q.oz_swing_percent.median():.1f}%), "
      f"whiff {b.whiff_percent:.1f}% (median {q.whiff_percent.median():.1f}%)")

# 4. Fast swingers who square up below average: does chase separate them?
fast = q.avg_swing_speed >= q.avg_swing_speed.quantile(0.85)
low_sq = q.squared_up_swing <= q.squared_up_swing.quantile(0.35)
g = q[fast & low_sq]
lo, hi = g[g.oz_swing_percent < 27], g[g.oz_swing_percent >= 27]
print(f"\n== Fast swingers (bat speed >= 85th pct) who square up below average (squared-up/swing <= 35th pct), "
      f"2025, 300+ PA: n={len(g)}")
print(f"   chase < 27%: n={len(lo)}, median xwOBA {lo.xwoba.median():.3f}  ({'; '.join(lo.name)})")
print(f"   chase 27%+:  n={len(hi)}, median xwOBA {hi.xwoba.median():.3f}")
b = q[q.player_id == ID].iloc[0]
print(f"   Barger: chase {b.oz_swing_percent:.1f}%, xwOBA {b.xwoba:.3f}, in group: {bool((fast & low_sq)[q.player_id == ID].iloc[0])}")

# 5. Fastball popups per batted ball (four-seamers, sinkers, cutters)
counts = {}
for bbt in ("popup", "fly_ball", "line_drive", "ground_ball"):
    d = savant_csv(f"/statcast_search/csv?all=true&hfSea=2025%7C&hfGT=R%7C&player_type=batter&hfBBT={bbt}%7C"
                   "&hfPT=FF%7CSI%7CFC%7C&group_by=name&min_pitches=0&min_results=0&min_pas=0"
                   "&sort_col=pitches&sort_order=desc")
    counts[bbt] = d.set_index("player_id").pitches
fb = pd.DataFrame(counts).fillna(0)
fb["bbe"] = fb.sum(axis=1)
fb["popup_rate"] = fb.popup / fb.bbe
fb = fb.join(q.set_index("player_id").pa, how="inner")  # 300+ PA pool
b = fb.loc[ID]
print(f"\n== Fastball popups per batted ball, 2025, 300+ PA (n={len(fb)}): Barger {b.popup_rate:.1%} "
      f"({b.popup:.0f}/{b.bbe:.0f}), median {fb.popup_rate.median():.1%}, "
      f"{pctile(fb.popup_rate, fb.index == ID):.0f}th pct")

# 6. Arm strength, 2025, 50+ throws
a = savant_csv("/leaderboard/arm-strength?type=player&year=2025&minThrows=50&pos=&team=&csv=true")
a["arm_overall"] = pd.to_numeric(a.arm_overall, errors="coerce")
a = a.dropna(subset=["arm_overall"])
me = a.player_id == ID
print(f"\n== Arm strength 2025 (50+ throws, n={len(a)}): {a[me].arm_overall.iloc[0]:.1f} mph, "
      f"{pctile(a.arm_overall, me):.0f}th pct")
