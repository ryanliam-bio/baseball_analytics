"""
contact_model.py -- the contact-point surface and contact-adjusted metrics.

Core idea
---------
For each swing i by hitter-season h:

    y_hi = a_h + f(depth, offbody, height) + g(pitch context) + e_hi

a_h is a hitter-season fixed effect, so f is learned only from how each hitter's
own swings change as his contact point moves. That matters: hitters who swing
harder also tend to meet the ball farther out front, so a pooled league curve
would credit the depth effect with some of that talent gap and over-penalise
out-front hitters.

f is a sum of cubic B-spline main effects plus pairwise tensor-product
interactions. g holds nuisance pitch context (count, pitch group, pitch speed),
so f is the effect of *where* contact happens with the pitch held fixed.

Contact-adjusted value of a swing = y - (f(c_hi) - f(c*)), where c* is the league
median contact point: "what this swing would have measured at a standard contact
point". A hitter's adjusted bat speed is the mean of those.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.preprocessing import SplineTransformer

MAIN_VARS = ("depth", "offbody", "height")
PAIRS = (("depth", "offbody"), ("depth", "height"), ("offbody", "height"))
COUNT_LEVELS = ["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2"]
GROUP_LEVELS = ["FB", "BR", "OS", "OTH"]


# ------------------------------------------------------------------ within-group algebra

def codes(keys: pd.Series) -> tuple[np.ndarray, int]:
    c, uniq = pd.factorize(keys)
    return c.astype(np.int64), len(uniq)


def group_mean(a: np.ndarray, g: np.ndarray, ng: int) -> np.ndarray:
    cnt = np.bincount(g, minlength=ng).astype(float)
    if a.ndim == 1:
        return np.bincount(g, a, ng) / cnt
    return np.column_stack([np.bincount(g, a[:, j], ng) for j in range(a.shape[1])]) / cnt[:, None]


def demean(a: np.ndarray, g: np.ndarray, ng: int) -> np.ndarray:
    return a - group_mean(a, g, ng)[g]


def solve_ls(X: np.ndarray, y: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    XtX = X.T @ X
    XtX[np.diag_indices_from(XtX)] += ridge * np.trace(XtX) / len(XtX)
    return np.linalg.solve(XtX, X.T @ y)


# ------------------------------------------------------------------ basis

@dataclass
class Surface:
    depth_var: str = "depth"                 # "depth" (inches) or "depth_ms"
    main_knots: int = 7
    pair_knots: int = 4
    interactions: bool = True
    context: bool = True                     # count + pitch group + pitch speed nuisance terms
    main_vars: tuple = MAIN_VARS
    transformers: dict = field(default_factory=dict)
    beta: np.ndarray | None = None
    n_contact: int = 0
    columns: list = field(default_factory=list)

    def _v(self, var: str) -> str:
        return self.depth_var if var == "depth" else var

    def _pairs(self):
        return [p for p in PAIRS if p[0] in self.main_vars and p[1] in self.main_vars]

    def _fit_transformers(self, df: pd.DataFrame) -> None:
        for var in self.main_vars:
            x = df[self._v(var)].to_numpy(float)
            for kind, nk in (("main", self.main_knots), ("pair", self.pair_knots)):
                knots = np.quantile(x, np.linspace(0.01, 0.99, nk))[:, None]
                st = SplineTransformer(knots=knots, degree=3, extrapolation="linear", include_bias=False)
                st.fit(x[:, None])
                self.transformers[(var, kind)] = st

    def contact_basis(self, df: pd.DataFrame) -> np.ndarray:
        blocks, names = [], []
        for var in self.main_vars:
            b = self.transformers[(var, "main")].transform(df[[self._v(var)]].to_numpy(float))
            blocks.append(b)
            names += [f"{var}_s{j}" for j in range(b.shape[1])]
        if self.interactions:
            for a, c in self._pairs():
                ba = self.transformers[(a, "pair")].transform(df[[self._v(a)]].to_numpy(float))
                bc = self.transformers[(c, "pair")].transform(df[[self._v(c)]].to_numpy(float))
                t = (ba[:, :, None] * bc[:, None, :]).reshape(len(df), -1)
                blocks.append(t)
                names += [f"{a}x{c}_{j}" for j in range(t.shape[1])]
        self.columns = names
        return np.hstack(blocks)

    @staticmethod
    def context_basis(df: pd.DataFrame) -> np.ndarray:
        cnt = pd.get_dummies(pd.Categorical(df["count"], categories=COUNT_LEVELS)).to_numpy(float)[:, 1:]
        grp = pd.get_dummies(pd.Categorical(df["pitch_group"], categories=GROUP_LEVELS)).to_numpy(float)[:, 1:]
        v = (df["release_speed"].to_numpy(float) - 90.0) / 5.0
        return np.hstack([cnt, grp, v[:, None], (v ** 2)[:, None]])

    def design(self, df: pd.DataFrame) -> np.ndarray:
        B = self.contact_basis(df)
        self.n_contact = B.shape[1]
        return np.hstack([B, self.context_basis(df)]) if self.context else B

    # -------------------------------------------------------------- fitting

    def fit(self, df: pd.DataFrame, y: str, groups: str | None = "hs") -> "Surface":
        """groups='hs' -> within hitter-season (fixed effects); None -> pooled with intercept."""
        if not self.transformers:
            self._fit_transformers(df)
        X = self.design(df)
        yy = df[y].to_numpy(float)
        if groups is None:
            X = np.hstack([np.ones((len(X), 1)), X])
            self.beta = solve_ls(X, yy)[1:]
        else:
            g, ng = codes(df[groups])
            self.beta = solve_ls(demean(X, g, ng), demean(yy, g, ng))
        return self

    def f(self, df: pd.DataFrame) -> np.ndarray:
        """Contact part of the prediction (no context, no intercept)."""
        return self.contact_basis(df) @ self.beta[: self.n_contact]

    def g(self, df: pd.DataFrame) -> np.ndarray:
        """Context part of the prediction."""
        if not self.context:
            return np.zeros(len(df))
        return self.context_basis(df) @ self.beta[self.n_contact:]

    def context_effects(self) -> dict:
        b = self.beta[self.n_contact:]
        eff = {f"count_{c}": b[i] for i, c in enumerate(COUNT_LEVELS[1:])}
        eff.update({f"group_{grp}": b[11 + i] for i, grp in enumerate(GROUP_LEVELS[1:])})
        return eff

    def partial(self, var: str, grid: np.ndarray, ref: dict) -> np.ndarray:
        """f along one contact variable with the others held at the reference point."""
        pts = pd.DataFrame({self._v(v): np.full(len(grid), ref[self._v(v)]) for v in self.main_vars})
        pts[self._v(var)] = grid
        return self.f(pts) - self.f(pd.DataFrame([{self._v(v): ref[self._v(v)] for v in self.main_vars}]))[0]


def reference_point(df: pd.DataFrame) -> dict:
    cols = ["depth", "depth_ms", "offbody", "height"]
    return {c: float(df[c].median()) for c in cols if c in df}


def adjust(df: pd.DataFrame, y: str, surf: Surface, f_ref: float | None = None,
           remove_context: bool = False) -> np.ndarray:
    """Per-swing contact-adjusted value (optionally also context-neutral).

    f_ref is the contact effect everyone is re-centred on. Default: the average
    contact effect over df, i.e. "this swing, if your contact point were the
    league's typical mix". That keeps the league mean unchanged, so a hitter's
    raw-minus-adjusted gap reads directly as how much his contact point helps
    or hurts him relative to everyone else.
    """
    f = surf.f(df)
    if f_ref is None:
        f_ref = float(f.mean())
    adj = df[y].to_numpy(float) - (f - f_ref)
    if remove_context and surf.context:
        adj = adj - surf.g(df)          # reference context = 0-0 count, fastball, 90 mph
    return adj


def oos_within_r2(df: pd.DataFrame, y: str, make_surface, n_folds: int = 5, seed: int = 1,
                  contact_only_score: bool = True) -> float:
    """Share of within-hitter-season variance in y explained out of sample.

    Folds split by batter, so a hitter's swings never inform his own prediction.
    Scored on the contact part only when contact_only_score is True.
    """
    rng = np.random.default_rng(seed)
    batters = df["batter"].unique()
    fold_of = dict(zip(batters, rng.integers(0, n_folds, len(batters))))
    fold = df["batter"].map(fold_of).to_numpy()
    ss_res = ss_tot = 0.0
    for k in range(n_folds):
        tr, te = df[fold != k], df[fold == k]
        s = make_surface().fit(tr, y)
        pred = s.f(te) if contact_only_score else s.f(te) + s.g(te)
        g, ng = codes(te["hs"])
        yd = demean(te[y].to_numpy(float), g, ng)
        pd_ = demean(pred, g, ng)
        ss_res += ((yd - pd_) ** 2).sum()
        ss_tot += (yd ** 2).sum()
    return 1 - ss_res / ss_tot


def variance_decomposition(df: pd.DataFrame, y: str) -> dict:
    g, ng = codes(df["hs"])
    v = df[y].to_numpy(float)
    total = v.var()
    within = demean(v, g, ng).var()
    return {"total_var": total, "between_share": 1 - within / total, "within_share": within / total}
