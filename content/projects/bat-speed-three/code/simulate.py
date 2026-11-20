"""
simulate.py -- synthetic 2024-26 swings in the savant_swings.py schema.

Used only to test the pipeline before the real files arrive. Every effect the
pipeline tries to estimate is planted here with a known size (see TRUTH), including
the traps: hitters who swing harder also tend to make contact farther out front
(so a pooled league curve overstates the depth effect), counts and pitch types
change bat speed partly *through* contact depth, check swings pile up deep and slow,
and depth values are clipped at Savant's -12 / 72 inch edges.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COUNTS = ["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2"]
COUNT_SHARE = np.array([.12, .08, .035, .005, .09, .10, .07, .035, .075, .13, .15, .11])
COUNT_SHARE = COUNT_SHARE / COUNT_SHARE.sum()

TRUTH = dict(
    depth_ref=30.0,
    within_slope=0.12,        # mph per inch farther out front (mean of hitter slopes)
    slope_sd=0.05,            # true hitter-to-hitter spread in that slope
    curvature=-0.0035,        # speed gain flattens way out front
    offbody_slope=0.06,       # mph per inch farther off the body
    height_quad=-2.0,         # mph * (zone-normalised height - 0.5)^2
    between_corr=0.40,        # corr(hitter speed, hitter mean depth): the confounder
    # counts: depth shift (inches) and direct speed effect (mph), relative to 0-0
    count_depth={"0-0": 0, "1-0": 1.0, "2-0": 1.5, "3-0": 2.0, "0-1": -1.5, "1-1": -0.5,
                 "2-1": 0.5, "3-1": 1.5, "0-2": -4.0, "1-2": -3.0, "2-2": -2.0, "3-2": -1.0},
    count_direct={"0-0": 0, "1-0": 0.2, "2-0": 0.4, "3-0": 0.5, "0-1": -0.3, "1-1": -0.1,
                  "2-1": 0.1, "3-1": 0.3, "0-2": -0.8, "1-2": -0.6, "2-2": -0.4, "3-2": -0.2},
    # pitch groups: offspeed met early (farther out front) but swung at slightly softer
    group_depth={"FB": 0.0, "BR": 3.0, "OS": 6.0},
    group_direct={"FB": 0.0, "BR": -0.3, "OS": -0.5},
)

PITCH_TYPES = {"FB": (["FF", "SI", "FC"], [.6, .25, .15], 94.0),
               "BR": (["SL", "ST", "CU", "KC"], [.45, .2, .25, .1], 84.5),
               "OS": (["CH", "FS"], [.8, .2], 86.0)}


def _hitter_pool(rng: np.random.Generator, n: int) -> pd.DataFrame:
    z1, z2 = rng.standard_normal(n), rng.standard_normal(n)
    r = TRUTH["between_corr"]
    return pd.DataFrame({
        "batter": np.arange(600000, 600000 + n),
        "speed_true": 71.0 + 3.0 * z1,
        "depth_mean": 30.0 + 3.5 * (r * z1 + np.sqrt(1 - r * r) * z2),
        "slope_true": rng.normal(TRUTH["within_slope"], TRUTH["slope_sd"], n),
        "contact_skill": rng.normal(0, 0.35, n),
        "path_trait": rng.normal(0, 0.35, n),
        "la_trait": rng.normal(0, 5, n),
        "stand": np.where(rng.random(n) < 0.45, "L", "R"),
        "sz_top": rng.normal(3.40, 0.10, n),
        "sz_bot": rng.normal(1.60, 0.08, n),
    })


def simulate(seasons=(2024, 2025, 2026), n_hitters: int = 800, per_season: int = 620,
             scale: float = 1.0, seed: int = 7) -> dict[int, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    pool = _hitter_pool(rng, n_hitters)
    out = {}
    for season in seasons:
        active = pool.sample(per_season, random_state=int(rng.integers(1e9))).reset_index(drop=True)
        active["speed_season"] = active["speed_true"] + rng.normal(0, 0.8, len(active))
        n_sw = np.clip(rng.lognormal(np.log(420), 0.75, len(active)) * scale, 15, 1300).astype(int)
        h = active.loc[np.repeat(active.index, n_sw)].reset_index(drop=True)
        n = len(h)

        count = rng.choice(COUNTS, n, p=COUNT_SHARE)
        group = rng.choice(["FB", "BR", "OS"], n, p=[.55, .28, .17])
        ptype = np.empty(n, dtype=object)
        velo = np.empty(n)
        for g, (types, w, v) in PITCH_TYPES.items():
            m = group == g
            ptype[m] = rng.choice(types, m.sum(), p=w)
            velo[m] = rng.normal(v, 2.5, m.sum())

        plate_x = rng.normal(0, 0.6, n)
        plate_z = rng.normal(2.45, 0.6, n)
        z_norm = (plate_z - h["sz_bot"].values) / (h["sz_top"].values - h["sz_bot"].values)
        away = np.where(h["stand"].values == "R", plate_x, -plate_x)

        c_depth = pd.Series(count).map(TRUTH["count_depth"]).to_numpy(float)
        c_direct = pd.Series(count).map(TRUTH["count_direct"]).to_numpy(float)
        g_depth = pd.Series(group).map(TRUTH["group_depth"]).to_numpy(float)
        g_direct = pd.Series(group).map(TRUTH["group_direct"]).to_numpy(float)

        depth = h["depth_mean"].values + g_depth + c_depth + rng.normal(0, 10.5, n)
        offbody = 37.0 + 7.0 * away + rng.normal(0, 4.0, n)
        d = depth - TRUTH["depth_ref"]
        speed = (h["speed_season"].values + h["slope_true"].values * d + TRUTH["curvature"] * d ** 2
                 + TRUTH["offbody_slope"] * (offbody - 37) + TRUTH["height_quad"] * (z_norm - 0.5) ** 2
                 + c_direct + g_direct + rng.normal(0, 2.4, n))
        junk = rng.random(n) < 0.03            # check swings: slow and deep
        speed[junk] = rng.uniform(15, 55, junk.sum())
        depth[junk] -= 10
        length = (7.3 + h["path_trait"].values + 0.075 * (speed - 71) + 0.035 * d
                  + 0.01 * (offbody - 37) + rng.normal(0, 0.35, n))
        length[junk] = rng.uniform(1.0, 5.0, junk.sum())

        dev = np.abs(depth - (h["depth_mean"].values + g_depth))
        logit = (-1.45 + 0.06 * (speed - 71) - h["contact_skill"].values + 0.45 * (group != "FB")
                 + 0.025 * dev)
        whiff = rng.random(n) < 1 / (1 + np.exp(-logit))
        in_play = ~whiff & (rng.random(n) < 0.48)
        desc = np.where(whiff, np.where(rng.random(n) < 0.08, "swinging_strike_blocked", "swinging_strike"),
                        np.where(in_play, "hit_into_play", np.where(rng.random(n) < 0.04, "foul_tip", "foul")))

        pitch_plate = velo - 8.0
        sq = rng.beta(9 + 2 * h["contact_skill"].values.clip(-1, 1), 2)
        ev = np.where(in_play, sq * (1.23 * speed + 0.23 * pitch_plate), np.nan)
        la = np.where(in_play, rng.normal(12 + h["la_trait"].values, 26), np.nan)
        barrel = (ev >= 98) & (la >= 26 - (ev - 98)) & (la <= 30 + 1.2 * (ev - 98))
        lsa = np.where(in_play, np.where(barrel, 6, rng.integers(1, 6, n)), np.nan)
        xw = np.where(in_play, np.clip(0.08 + 0.03 * (ev - 75) * np.exp(-((la - 18) / 22) ** 2), 0, 2), np.nan)

        vy0 = -1.4667 * velo * 0.985
        ay = rng.normal(np.where(group == "FB", 29, 25), 2.5)
        missing = rng.random(n) < np.where(in_play, 0.05, 0.02)
        is_bunt = rng.random(n) < 0.008
        depth_clipped = np.clip(depth, -12, 72)
        miss = np.where(whiff, np.abs(rng.normal(0, 2.5, n)) + 0.1 * dev, np.nan)

        dates = pd.to_datetime(f"{season}-03-28") + pd.to_timedelta(rng.integers(0, 184, n), unit="D")
        df = pd.DataFrame({
            "game_date": dates, "game_year": season, "game_type": "R",
            "game_pk": rng.integers(740000, 790000, n), "at_bat_number": rng.integers(1, 80, n),
            "pitch_number": rng.integers(1, 8, n), "inning": rng.integers(1, 10, n),
            "batter": h["batter"].values, "pitcher": rng.integers(500000, 560000, n),
            "player_name": "Hitter " + h["batter"].astype(str).values,
            "stand": h["stand"].values, "p_throws": rng.choice(["R", "L"], n, p=[.72, .28]),
            "balls": [int(c[0]) for c in count], "strikes": [int(c[2]) for c in count],
            "pitch_type": ptype, "release_speed": velo.round(1), "release_extension": rng.normal(6.4, .4, n),
            "plate_x": plate_x.round(2), "plate_z": plate_z.round(2),
            "sz_top": h["sz_top"].values.round(2), "sz_bot": h["sz_bot"].values.round(2),
            "vx0": rng.normal(5, 5, n), "vy0": vy0, "vz0": rng.normal(-5, 3, n),
            "ax": rng.normal(-5, 8, n), "ay": ay, "az": rng.normal(-20, 9, n),
            "type": np.where(in_play, "X", "S"), "description": desc,
            "launch_speed": ev.round(1), "launch_angle": np.round(la),
            "launch_speed_angle": lsa, "estimated_woba_using_speedangle": xw.round(3),
            "bat_speed": np.where(missing, np.nan, speed.round(1)),
            "swing_length": np.where(missing, np.nan, np.clip(length, 0.2, 14).round(1)),
            "attack_angle": np.where(missing, np.nan, rng.normal(10, 8, n).round(1)),
            "intercept_ball_minus_batter_pos_x_inches": np.where(missing, np.nan, offbody.round(2)),
            "intercept_ball_minus_batter_pos_y_inches": np.where(missing, np.nan, depth_clipped.round(2)),
            "miss_distance": np.where(missing, np.nan, miss.round(2)),
            "is_bunt": is_bunt,
        })
        out[season] = df
    return out, pool


if __name__ == "__main__":
    import time
    t = time.time()
    data, pool = simulate()
    for s, df in data.items():
        print(s, df.shape, f"{df.bat_speed.notna().mean():.3f}")
    print(f"{time.time() - t:.1f}s")
