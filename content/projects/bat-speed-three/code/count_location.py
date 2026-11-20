"""
count_location.py -- count effects on bat speed, within hitter, with pitch location controls.

    python count_location.py --data path/to/swings_2024.parquet path/to/swings_2025.parquet path/to/swings_2026.parquet

Controls: pitch type, pitch velocity, pitch location (side-adjusted horizontal position and
zone-relative height, plus Savant zone), and platoon. Each count is then split into the part
that comes with a shallower/deeper contact point and the part at the same contact point.

Writes:
  results/mediation_count_location.csv        every count vs 0-0  (figures.py uses this for count-breakdown)
  results/mediation_count_state_location.csv  2.0's Tango buckets vs neutral
  results/count_controls_ladder.csv           pitcher's/hitter's count effect as controls are added
"""
from __future__ import annotations

import argparse
import gc
from pathlib import Path

import numpy as np
import pandas as pd

import contact_model as cm
import context as cx
import prep

HIT = {"3-0", "3-1", "2-0", "3-2"}          # Tango buckets used in 2.0
PIT = {"0-1", "1-2", "0-2", "2-2"}
TYPES = ["FF", "SI", "FC", "SL", "ST", "SV", "CU", "KC", "CH", "FS"]


def dummies(s: pd.Series, levels: list[str] | None = None) -> np.ndarray:
    cat = pd.Categorical(s.astype(str), categories=levels) if levels else pd.Categorical(s.astype(str))
    return pd.get_dummies(cat).to_numpy(np.float32)[:, 1:]


def controls(df: pd.DataFrame, level: str) -> np.ndarray:
    v = ((df["release_speed"].to_numpy(float) - 90) / 5).astype(np.float32)
    blocks = [dummies(df["pitch_type"].astype(str).where(df["pitch_type"].astype(str).isin(TYPES), "OTH")),
              np.column_stack([v, v ** 2])]
    if level == "type+velo":
        return np.hstack(blocks)
    side = (np.where(df["stand"].astype(str) == "R", 1, -1) * df["plate_x"].to_numpy(float)).astype(np.float32)
    h = df["height"].to_numpy(np.float32)
    blocks += [np.column_stack([side, side ** 2, side ** 3, h, h ** 2, h ** 3, side * h]),
               dummies(df["zone"].astype("Int64").astype(str)),
               (df["stand"].astype(str) == df["p_throws"].astype(str)).to_numpy(np.float32)[:, None]]
    return np.hstack(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", default=[f"data/swings_{y}.parquet" for y in (2024, 2025, 2026)])
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(exist_ok=True)

    raw = prep.load(args.data)
    base, audit = prep.base_filter(raw)
    sw = prep.tracked_swings(base, audit)
    comp = sw[sw["competitive_iqr"]].reset_index(drop=True)
    del raw, base, sw
    gc.collect()
    comp["count_state"] = np.where(comp["count"].isin(HIT), "hitter",
                                   np.where(comp["count"].isin(PIT), "pitcher", "neutral"))
    print(f"{len(comp):,} competitive swings")

    # additive contact surface keeps memory manageable on a laptop
    surf = cm.Surface(interactions=False).fit(comp, "bat_speed")
    gc.collect()

    ladder = []
    states = ["neutral", "hitter", "pitcher"]
    for label, ctrl in (("none", None), ("pitch type + velo", controls(comp, "type+velo")),
                        ("+ location + platoon", controls(comp, "full"))):
        eff = cx.within_effects(comp, "count_state", states, "bat_speed", None, ctrl)
        ladder.append({"controls": label, "hitter_vs_neutral": eff["hitter"], "pitcher_vs_neutral": eff["pitcher"]})
        del ctrl
        gc.collect()
    full = controls(comp, "full")
    eff = cx.within_effects(comp, "count_state", states, "bat_speed", surf, full)
    ladder.append({"controls": "+ contact point", "hitter_vs_neutral": eff["hitter"], "pitcher_vs_neutral": eff["pitcher"]})
    ladder = pd.DataFrame(ladder).round(2)
    ladder.to_csv(out / "count_controls_ladder.csv", index=False)
    print("\nPitcher's / hitter's counts vs neutral (mph, within hitter):")
    print(ladder.to_string(index=False))

    state = cx.mediation(comp, "count_state", states, surf, full)
    state.round(3).to_csv(out / "mediation_count_state_location.csv")
    print("\nTango buckets, split by contact point (location-controlled):")
    print(state.round(2).to_string())

    by_count = cx.mediation(comp, "count", cm.COUNT_LEVELS, surf, full)
    by_count.round(3).to_csv(out / "mediation_count_location.csv")
    print("\nEvery count vs 0-0 (location-controlled):")
    print(by_count.round(2).to_string())


if __name__ == "__main__":
    main()
