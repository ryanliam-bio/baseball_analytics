"""
context.py -- does count / pitch type change bat speed directly, or through contact depth?

Total effect  : within-hitter model with only the context dummies (plus pitch speed).
Direct effect : same model plus the contact surface f(depth, offbody, height).
Share through contact = 1 - direct / total.
Depth shift   : within-hitter change in contact depth for the same contrast.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import contact_model as cm

MAIN_TYPES = ["FF", "SI", "FC", "SL", "ST", "CU", "KC", "CH", "FS", "SV"]


def _dummies(s: pd.Series, levels: list[str]) -> np.ndarray:
    return pd.get_dummies(pd.Categorical(s, categories=levels)).to_numpy(float)[:, 1:]


def within_effects(sw: pd.DataFrame, factor: str, levels: list[str], y: str = "bat_speed",
                   surface: cm.Surface | None = None, extra: np.ndarray | None = None) -> pd.Series:
    D = _dummies(sw[factor], levels)
    blocks = [D]
    if extra is not None:
        blocks.append(extra)
    if surface is not None:
        blocks.append(surface.contact_basis(sw))
    X = np.hstack(blocks)
    g, ng = cm.codes(sw["hs"])
    beta = cm.solve_ls(cm.demean(X, g, ng), cm.demean(sw[y].to_numpy(float), g, ng))
    return pd.Series(beta[: D.shape[1]], index=levels[1:])


def mediation(sw: pd.DataFrame, factor: str, levels: list[str], surface: cm.Surface,
              controls: np.ndarray | None = None) -> pd.DataFrame:
    total = within_effects(sw, factor, levels, "bat_speed", None, controls)
    direct = within_effects(sw, factor, levels, "bat_speed", surface, controls)
    depth = within_effects(sw, factor, levels, "depth", None, controls)
    depth_ms = within_effects(sw, factor, levels, "depth_ms", None, controls)
    out = pd.DataFrame({"total_mph": total, "direct_mph": direct, "via_contact_mph": total - direct,
                        "depth_shift_in": depth, "depth_shift_ms": depth_ms})
    present = sw[factor].astype(str).value_counts()
    out["swings"] = [int(present.get(l, 0)) for l in out.index]
    out = out[out["swings"] > 0]
    # a share is only meaningful when there is a real total effect to split
    out["share_via_contact"] = (out["via_contact_mph"] / out["total_mph"]).where(out["total_mph"].abs() >= 0.2)
    out.index.name = f"{factor} (vs {levels[0]})"
    return out


def pitch_speed_controls(sw: pd.DataFrame) -> np.ndarray:
    v = (sw["release_speed"].to_numpy(float) - 90) / 5
    return np.column_stack([v, v ** 2])


def raw_vs_adjusted_by(sw: pd.DataFrame, by: str, levels: list[str] | None = None) -> pd.DataFrame:
    d = sw if levels is None else sw[sw[by].isin(levels)]
    t = d.groupby(by, observed=True).agg(swings=("bat_speed", "size"), raw=("bat_speed", "mean"),
                                         adjusted=("bat_speed_adj", "mean"), depth=("depth", "mean"),
                                         depth_ms=("depth_ms", "mean"))
    return t.sort_values("raw", ascending=False)


# ------------------------------------------------------------------ timing by pitch type

def timing_shift(sw: pd.DataFrame, min_each: int = 40) -> pd.DataFrame:
    """Per hitter-season: mean contact depth (ms) on breaking / offspeed minus on fastballs."""
    p = sw.pivot_table(index="hs", columns="pitch_group", values="depth_ms", aggfunc=["mean", "size"])
    out = pd.DataFrame(index=p.index)
    for grp in ("BR", "OS"):
        ok = (p[("size", grp)] >= min_each) & (p[("size", "FB")] >= min_each)
        out[f"shift_{grp}_ms"] = (p[("mean", grp)] - p[("mean", "FB")]).where(ok)
    return out


def whiff_anatomy(base_swings: pd.DataFrame, min_contact: int = 30) -> pd.DataFrame:
    """Whiffs relative to the hitter's own contact depth for that pitch group.

    depth_dev_ms > 0: he was early (bat reached the ball's path in front of his usual spot);
    < 0: late. miss_distance (when present) separates timing misses from path misses.
    """
    contact = base_swings[~base_swings["is_whiff"]]
    norm = contact.groupby(["hs", "pitch_group"])["depth_ms"].agg(["mean", "std", "size"])
    norm = norm[norm["size"] >= min_contact]
    wh = base_swings[base_swings["is_whiff"]].join(norm, on=["hs", "pitch_group"], how="inner")
    wh = wh.assign(depth_dev_ms=wh["depth_ms"] - wh["mean"], depth_z=(wh["depth_ms"] - wh["mean"]) / wh["std"])
    return wh
