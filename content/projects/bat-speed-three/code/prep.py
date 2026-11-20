"""
prep.py -- cleaning, derived swing features, and hitter-season outcomes.

Conventions (checked against the real coverage report):
  depth   = intercept_ball_minus_batter_pos_y_inches   (+ = out in front of the hitter's CoM)
  offbody = intercept_ball_minus_batter_pos_x_inches   (already batter-relative; + for both sides)
  height  = plate_z scaled to the hitter's own zone: 0 = bottom, 1 = top
"""
from __future__ import annotations

import numpy as np
import pandas as pd

IX = "intercept_ball_minus_batter_pos_x_inches"
IY = "intercept_ball_minus_batter_pos_y_inches"
DEPTH_EDGES = (-12.0, 72.0)          # Savant clips depth at these values
FRONT_OF_PLATE_FT = 17 / 12

WHIFF = {"swinging_strike", "swinging_strike_blocked"}
PITCH_GROUP = {
    "FF": "FB", "SI": "FB", "FC": "FB", "FA": "FB",
    "SL": "BR", "ST": "BR", "SV": "BR", "CU": "BR", "KC": "BR", "CS": "BR", "SC": "BR",
    "CH": "OS", "FS": "OS", "FO": "OS", "KN": "OS", "EP": "OS",
}
# Count buckets follow the run-value split used in 2.0 (Tango RE288): counts that
# favour the hitter vs the pitcher, with 0-0, 1-1 and 3-2 left neutral.
HITTER_COUNTS = {"1-0", "2-0", "3-0", "2-1", "3-1"}
PITCHER_COUNTS = {"0-1", "0-2", "1-2", "2-2"}


def load(paths) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


def swing_order_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in ["game_date", "game_pk", "at_bat_number", "pitch_number"] if c in df]


def base_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Regular season, no bunts. Returns frame used for outcomes (tracked or not)."""
    audit = {"rows_in": len(df)}
    if "game_type" in df:
        df = df[df["game_type"].astype(str) == "R"]
    audit["after_regular_season"] = len(df)
    df = df[~df["is_bunt"].astype(bool)]
    audit["after_no_bunts"] = len(df)
    df = df.copy()
    df["season"] = df["game_year"].astype(int)
    df["hs"] = df["season"].astype(np.int64) * 1_000_000 + df["batter"].astype(np.int64)
    df["is_whiff"] = df["description"].astype(str).isin(WHIFF)
    df["is_bbe"] = df["description"].astype(str).str.startswith("hit_into_play") & df["launch_speed"].notna()
    return df.sort_values(["season", "batter"] + swing_order_cols(df)).reset_index(drop=True), audit


def tracked_swings(df: pd.DataFrame, audit: dict) -> pd.DataFrame:
    need = ["bat_speed", "swing_length", IX, IY, "plate_x", "plate_z", "sz_top", "sz_bot",
            "vy0", "ay", "release_speed"]
    df = df.dropna(subset=[c for c in need if c in df])
    audit["after_tracking_complete"] = len(df)
    at_edge = (df[IY] <= DEPTH_EDGES[0] + 0.05) | (df[IY] >= DEPTH_EDGES[1] - 0.05)
    audit["depth_at_clip_edges"] = int(at_edge.sum())
    df = df[~at_edge].copy()
    audit["after_depth_edges"] = len(df)

    df["depth"] = df[IY].astype(float)
    df["offbody"] = df[IX].astype(float)
    zone_h = (df["sz_top"] - df["sz_bot"]).where(lambda s: s > 0.5)
    df["height"] = ((df["plate_z"] - df["sz_bot"]) / zone_h).astype(float)
    df = df[df["height"].between(-1.5, 2.5)]
    audit["after_height_sanity"] = len(df)

    # Ball's speed toward the hitter at the front of the plate -> inches per millisecond.
    vy_sq = df["vy0"] ** 2 + 2 * df["ay"] * (FRONT_OF_PLATE_FT - 50.0)
    df["ball_in_per_ms"] = np.sqrt(vy_sq.clip(lower=1)) * 12 / 1000
    df["depth_ms"] = df["depth"] / df["ball_in_per_ms"]   # ms of lead before ball reaches CoM plane

    df["pitch_group"] = df["pitch_type"].astype(str).map(PITCH_GROUP).fillna("OTH")
    df["count"] = df["balls"].astype(int).astype(str) + "-" + df["strikes"].astype(int).astype(str)
    df["count_state"] = np.where(df["count"].isin(HITTER_COUNTS), "hitter",
                                 np.where(df["count"].isin(PITCHER_COUNTS), "pitcher", "neutral"))
    df["impulse"] = df["bat_speed"] ** 2 / df["swing_length"].clip(lower=0.5)

    # Competitive-swing flags. Primary = 2.0's rule (drop below Q1 - 1.5*IQR per hitter-season).
    g = df.groupby("hs")["bat_speed"]
    q1, q3 = g.transform(lambda s: s.quantile(0.25)), g.transform(lambda s: s.quantile(0.75))
    df["competitive_iqr"] = df["bat_speed"] >= q1 - 1.5 * (q3 - q1)
    df["competitive_50"] = df["bat_speed"] >= 50
    audit["iqr_removed"] = int((~df["competitive_iqr"]).sum())
    return df.reset_index(drop=True)


def ev50(ev: pd.Series) -> float:
    ev = ev.dropna().sort_values(ascending=False)
    return ev.iloc[: max(1, len(ev) // 2)].mean() if len(ev) else np.nan


def outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Hitter-season outcomes from all non-bunt swings (tracked or not)."""
    bbe = df[df["is_bbe"]]
    g_sw = df.groupby("hs")
    g_b = bbe.groupby("hs")
    out = pd.DataFrame({
        "season": g_sw["season"].first(),
        "batter": g_sw["batter"].first(),
        "name": g_sw["player_name"].first().astype(str),
        "swings_all": g_sw.size(),
        "whiff_rate": g_sw["is_whiff"].mean(),
        "bbe": g_b.size(),
        "ev50": g_b["launch_speed"].apply(ev50),
        "hardhit_rate": g_b["launch_speed"].apply(lambda s: (s >= 95).mean()),
        "barrel_rate": g_b["launch_speed_angle"].apply(lambda s: (s == 6).mean()),
        "xwobacon": g_b["estimated_woba_using_speedangle"].mean(),
    })
    out["bbe"] = out["bbe"].fillna(0).astype(int)
    return out


def data_quality(df_all: pd.DataFrame) -> dict:
    """Checks flagged from the coverage report."""
    q = {}
    tr = df_all["bat_speed"].notna()
    q["tracking_by_month"] = (df_all.assign(month=df_all["game_date"].dt.to_period("M").astype(str), tr=tr)
                              .groupby(["season", "month"])["tr"].mean().round(3).to_dict())
    iy = df_all[IY]
    q["depth_edge_share"] = (((iy <= -11.95) | (iy >= 71.95)).groupby(df_all["season"]).mean()
                             .round(4).to_dict())
    bbe = df_all[df_all["is_bbe"]]
    miss = bbe["bat_speed"].isna()
    q["bbe_untracked_share"] = miss.groupby(bbe["season"]).mean().round(4).to_dict()
    q["bbe_ev_tracked_vs_untracked"] = bbe.groupby(miss)["launch_speed"].describe()[
        ["count", "mean", "25%", "50%", "75%"]].round(1).to_dict("index")
    q["bbe_la_tracked_vs_untracked"] = bbe.groupby(miss)["launch_angle"].describe()[
        ["mean", "25%", "50%", "75%"]].round(1).to_dict("index")
    q["lefty_swing_share"] = (df_all["stand"].astype(str) == "L").groupby(df_all["season"]).mean().round(3).to_dict()
    if "miss_distance" in df_all:
        md = df_all["miss_distance"]
        q["miss_distance_nonnull_by_desc"] = (md.notna().groupby(df_all["description"].astype(str))
                                              .mean().round(3).to_dict())
        q["miss_distance_summary"] = md.describe(percentiles=[.01, .1, .5, .9, .99]).round(2).to_dict()
    return q
