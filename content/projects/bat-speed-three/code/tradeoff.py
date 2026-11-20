"""
tradeoff.py -- what does letting it travel cost each hitter?

For every swing we already have the league within-hitter surface f and the context
effects g. The residual e = y - a_h - f(c) - g(ctx) is what the league model can't
explain. If a hitter loses *more* bat speed than the league when he gets deep, his
residuals trend upward with depth. So per hitter-season we fit

    e_hi = d_h * (depth_hi - mean depth_h) + noise

d_h is his depth sensitivity relative to the league curve (mph per inch, or per ms
when the surface uses depth_ms). His total local slope = league slope at his typical
contact point + d_h. Estimates are shrunk toward zero with an empirical-Bayes
(method-of-moments) prior, since a few hundred swings pin a slope down poorly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import contact_model as cm


def residuals(sw: pd.DataFrame, surf: cm.Surface, y: str = "bat_speed") -> np.ndarray:
    g, ng = cm.codes(sw["hs"])
    fit = surf.f(sw) + surf.g(sw)
    return cm.demean(sw[y].to_numpy(float) - fit, g, ng)


def hitter_slopes(sw: pd.DataFrame, resid: np.ndarray, depth_col: str = "depth",
                  min_swings: int = 150) -> pd.DataFrame:
    d = pd.DataFrame({"hs": sw["hs"].to_numpy(), "e": resid, "x": sw[depth_col].to_numpy(float)})
    d["xc"] = d["x"] - d.groupby("hs")["x"].transform("mean")
    agg = d.assign(xy=d["xc"] * d["e"], xx=d["xc"] ** 2).groupby("hs").agg(
        n=("e", "size"), sxy=("xy", "sum"), sxx=("xx", "sum"), mean_x=("x", "mean"))
    agg = agg[agg["n"] >= min_swings]
    agg["slope"] = agg["sxy"] / agg["sxx"]
    d = d[d["hs"].isin(agg.index)]
    fitted = d["xc"] * d["hs"].map(agg["slope"])
    rss = (d["e"] - fitted).pow(2).groupby(d["hs"]).sum()
    agg["se"] = np.sqrt(rss / (agg["n"] - 2) / agg["sxx"])
    return shrink(agg)


def shrink(agg: pd.DataFrame) -> pd.DataFrame:
    """Method-of-moments (DerSimonian-Laird) random-effects shrinkage toward the mean."""
    w = 1 / agg["se"] ** 2
    mu = np.average(agg["slope"], weights=w)
    q = (w * (agg["slope"] - mu) ** 2).sum()
    tau2 = max(0.0, (q - (len(agg) - 1)) / (w.sum() - (w ** 2).sum() / w.sum()))
    k = tau2 / (tau2 + agg["se"] ** 2)
    agg = agg.copy()
    agg["slope_shrunk"] = mu + k * (agg["slope"] - mu)
    agg["reliability"] = k
    agg.attrs.update(tau=np.sqrt(tau2), mu=mu)
    return agg


def split_half_slopes(sw: pd.DataFrame, resid: np.ndarray, depth_col: str = "depth",
                      min_swings: int = 300) -> float:
    half = sw.groupby("hs").cumcount().to_numpy() % 2
    a = hitter_slopes(sw[half == 0], resid[half == 0], depth_col, min_swings // 2)
    b = hitter_slopes(sw[half == 1], resid[half == 1], depth_col, min_swings // 2)
    both = a.index.intersection(b.index)
    r = a.loc[both, "slope"].corr(b.loc[both, "slope"])
    return 2 * r / (1 + r) if r > -1 else np.nan


def league_local_slope(surf: cm.Surface, ref: dict, at: np.ndarray, var: str = "depth",
                       h: float = 1.0) -> np.ndarray:
    """Derivative of the league contact curve along depth at each hitter's mean depth."""
    up = surf.partial(var, at + h, ref)
    dn = surf.partial(var, at - h, ref)
    return (up - dn) / (2 * h)
