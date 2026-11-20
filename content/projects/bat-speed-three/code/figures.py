"""
figures.py -- static PNGs for the write-up, built from ./results.

Palette: validated default (dataviz skill). Slot 1 blue = the contact-adjusted /
within-hitter series (the story), slot 2 orange = raw / naive comparison.
Diverging (contact credit): blue <-> red with a gray midpoint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker as mticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8983", "#e6e5e1"
BLUE, ORANGE, RED, NEUTRAL = "#2a78d6", "#eb6834", "#e34948", "#c9c8c3"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10.5, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 0, "ytick.major.size": 0,
    "axes.axisbelow": True, "lines.linewidth": 2, "lines.solid_capstyle": "round", "legend.frameon": False,
})

LABELS = {
    "bat_speed": "Bat speed", "bat_speed_adj": "Contact-adjusted bat speed",
    "swing_length": "Swing length", "swing_length_adj": "Contact-adjusted swing length",
    "impulse": "Impulse (v²/L)", "impulse_adj": "Contact-adjusted impulse",
    "barrel_rate": "Barrel%", "ev50": "EV50", "hardhit_rate": "Hard-hit%", "xwobacon": "xwOBAcon",
    "whiff_rate": "Whiff%",
}


def _save(fig, out: Path, name: str, note: str | None = None):
    if note:
        fig.text(0.01, 0.01, note, color=MUTED, fontsize=8.5, ha="left", va="bottom")
    fig.savefig(out / name, dpi=200, bbox_inches="tight")
    plt.close(fig)


def contact_curves(res: Path, out: Path):
    c = pd.read_csv(res / "contact_curves.csv")
    c = c[c["model"] == "within"]
    spec = [("depth", "Contact depth (in front of body, in)", "Depth"),
            ("offbody", "Horizontal distance off batter COM (in)", "Away from batter"),
            ("height", "Pitch height (0 = bottom of zone, 1 = top)", "Height")]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9), sharey=True)
    for ax, (var, xlabel, title) in zip(axes, spec):
        d = c[c["var"] == var]
        ax.plot(d["x"], d["mph"], color=BLUE)
        if var == "depth":
            pk = d.loc[d["mph"].idxmax()]
            ax.plot([pk["x"]], [pk["mph"]], "o", color=BLUE, ms=7, markeredgecolor=SURFACE, markeredgewidth=2)
            ax.annotate(f"peak {pk['mph']:+.1f} mph at {pk['x']:.0f} in", (pk["x"], pk["mph"]),
                        textcoords="offset points", xytext=(0, 9), ha="center", color=INK2, fontsize=9)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xlabel(xlabel)
        ax.set_title(title)
    axes[0].set_ylabel("Bat speed Δ vs. typical contact (mph)")
    fig.suptitle("Same hitter, different contact point", x=0.01, ha="left", fontweight="bold", fontsize=13)
    fig.tight_layout()
    _save(fig, out, "fig1_contact_curves.png",
          "Within-hitter bat speed shifts (hitter-season fixed effects, count / pitch type / velo held fixed). "
          "Other two dimensions at league median. 2024-26, 924k competitive swings.")


def stabilization(res: Path, out: Path):
    a = pd.read_csv(res / "stabilization_fine.csv")
    b = pd.read_csv(res / "stabilization_fine_length.csv")
    s = pd.concat([a, b])
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
    for ax, (raw, adj, title) in zip(axes, (("bat_speed", "bat_speed_adj", "Bat speed"),
                                            ("swing_length", "swing_length_adj", "Swing length"))):
        for m, color, lab in ((raw, ORANGE, "Raw"), (adj, BLUE, "Contact-adjusted")):
            d = s[s["metric"] == m]
            ax.plot(d["n"], d["r_rest"], color=color, label=lab, marker="o", ms=4.5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.axhline(0.9, color=INK2, lw=0.8)
        ax.set_xscale("log")
        ax.set_xticks([2, 5, 10, 20, 50])
        ax.set_xticklabels(["2", "5", "10", "20", "50"])
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel("Swings observed")
        ax.set_title(title)
    axes[0].set_ylabel("r with rest-of-season mean")
    axes[0].legend(loc="lower right")
    fig.tight_layout()
    _save(fig, out, "fig2_stabilization.png",
          "First n swings vs. ROS mean (no overlap). 979 hitter-seasons with 400+ swings. Line at r = 0.9.")


def forest(res: Path, out: Path):
    d = pd.read_csv(res / "adjusted_minus_raw_bootstrap.csv")
    d = d[d["adjusted"].isin(["bat_speed_adj", "swing_length_adj", "impulse_adj"])]
    blocks = [("bat_speed_adj", "Bat speed"), ("swing_length_adj", "Swing length"), ("impulse_adj", "Impulse")]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharex=True, sharey=True)
    outcomes = ["barrel_rate", "ev50", "hardhit_rate", "xwobacon", "whiff_rate"]
    for ax, (adj, title) in zip(axes, blocks):
        for j, (window, color, off) in enumerate((("same", ORANGE, 0.14), ("next", BLUE, -0.14))):
            dd = d[(d["adjusted"] == adj) & (d["window"] == window)].set_index("outcome").loc[outcomes]
            y = np.arange(len(outcomes))[::-1] + off
            ax.hlines(y, dd["ci_lo"], dd["ci_hi"], color=color, lw=2)
            ax.plot(dd["r_diff"], y, "o", color=color, ms=6, markeredgecolor=SURFACE, markeredgewidth=1.5,
                    label="Same season" if window == "same" else "Next season")
        ax.axvline(0, color=INK2, lw=0.8)
        ax.set_yticks(np.arange(len(outcomes))[::-1])
        ax.set_yticklabels([LABELS[o] for o in outcomes])
        ax.set_title(title)
        ax.set_xlabel("r(adjusted) − r(raw)")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4, symmetric=True))
        ax.grid(axis="y", visible=False)
    axes[0].legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    _save(fig, out, "fig3_adjusted_minus_raw.png",
          "Left of zero = raw speed predicts outcomes better than adjusted. 95% intervals from resampling hitters.")


def _first_last(name: str) -> str:
    return " ".join(reversed([p.strip() for p in str(name).split(",", 1)])) if "," in str(name) else str(name)


def depth_cost(res: Path, out: Path, k: int = 10):
    lb = pd.read_csv(res / "depth_cost_leaderboard.csv").sort_values("mph_per_ms")
    med = lb["mph_per_ms"].median()
    pick = pd.concat([lb.head(k), lb.tail(k)]).reset_index(drop=True)
    y = np.arange(len(pick))[::-1]
    fig, ax = plt.subplots(figsize=(8, 6.4))
    ax.axvline(med, color=INK2, lw=0.8)
    ax.text(med, -0.9, f" league median {med:.2f}", color=INK2, fontsize=9, va="center")
    colors = [BLUE] * k + [ORANGE] * k
    ax.hlines(y, med, pick["mph_per_ms"], color=NEUTRAL, lw=2)
    ax.scatter(pick["mph_per_ms"], y, s=60, c=colors, edgecolors=SURFACE, linewidths=2, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([_first_last(n) for n in pick["name"]])
    ax.set_xlabel("mph of bat speed per extra millisecond out front")
    ax.set_title("Who can let it travel, and who pays for it")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, out, "fig4_depth_cost.png",
          "2024-26 pooled, 1,000+ competitive swings. Blue = minimal speed loss when letting it travel; "
          "orange = steepest drop. Shrunk toward league.")


def count_mediation(res: Path, out: Path):
    loc = res / "mediation_count_location.csv"
    m = pd.read_csv(loc if loc.exists() else res / "mediation_count.csv").set_index("count (vs 0-0)")
    note = ("Controls: pitch type, velocity, location, and platoon." if loc.exists()
            else "Controls: pitch group and pitch speed.")
    order = ["3-0", "2-0", "3-1", "1-0", "2-1", "1-1", "3-2", "0-1", "2-2", "1-2", "0-2"]
    m = m.loc[[o for o in order if o in m.index]]
    y = np.arange(len(m))[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.barh(y, m["direct_mph"], height=0.55, color=BLUE, label="Same contact point (effort / intent)")
    # stack the contact-depth piece on the end of the blue bar, or start it at zero if it points the other way
    left = np.where(np.sign(m["via_contact_mph"]) == np.sign(m["direct_mph"]), m["direct_mph"], 0)
    ax.barh(y, m["via_contact_mph"], left=left, height=0.55, color=ORANGE,
            edgecolor=SURFACE, linewidth=2, label="Through contact depth")
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(m.index)
    ax.set_xlabel("Bat speed vs. 0-0 (mph, within hitter)")
    ax.set_title("Where the count effect comes from")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, out, "fig5_count_mediation.png", note)


def pitch_types(res: Path, out: Path):
    t = pd.read_csv(res / "bat_speed_by_pitch_type.csv").set_index("pitch_type").sort_values("raw")
    y = np.arange(len(t))
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.hlines(y, t["raw"], t["adjusted"], color=NEUTRAL, lw=2)
    ax.plot(t["raw"], y, "o", color=ORANGE, ms=7, markeredgecolor=SURFACE, markeredgewidth=1.5, label="Raw")
    ax.plot(t["adjusted"], y, "o", color=BLUE, ms=7, markeredgecolor=SURFACE, markeredgewidth=1.5,
            label="Contact-adjusted")
    ax.set_yticks(y)
    ax.set_yticklabels(t.index)
    ax.set_xlabel("Mean bat speed (mph)")
    ax.set_title("Bat speed by pitch type, before and after contact point")
    ax.legend(loc="upper left")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, out, "fig6_pitch_type.png")


def contact_credit(res: Path, out: Path, season: int | None = None, min_n: int = 400, k: int = 10):
    t = pd.read_csv(res / "hitter_seasons.csv")
    season = season or int(t["season"].max())
    t = t[(t["season"] == season) & (t["n"] >= min_n)].sort_values("contact_effect")
    pick = pd.concat([t.head(k), t.tail(k)])
    y = np.arange(len(pick))
    fig, ax = plt.subplots(figsize=(8, 6.2))
    colors = np.where(pick["contact_effect"] > 0, RED, BLUE)
    ax.barh(y, pick["contact_effect"], height=0.6, color=colors)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{_first_last(n)}  ({r:.1f} → {a:.1f})" for n, r, a in
                        zip(pick["name"], pick["bat_speed"], pick["bat_speed_adj"])], fontsize=9)
    ax.set_xlabel("mph of raw bat speed explained by contact point")
    ax.set_title(f"{season}: who gets the most (and least) bat speed from their contact point")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, out, "fig7_contact_credit.png",
          f"Red = contact point inflates raw bat speed; blue = deflates. {min_n}+ competitive swings. Labels: raw → adjusted mph.")


def whiff_timing(res: Path, out: Path):
    h = pd.read_csv(res / "whiff_timing_hist.csv")
    summ = pd.read_csv(res / "whiff_timing_summary.csv").set_index("pitch_group")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for g, color, lab in (("FB", BLUE, "Fastballs"), ("BR", ORANGE, "Breaking"), ("OS", "#1baf7a", "Offspeed")):
        d = h[h["pitch_group"] == g]
        x = d["left"] + 1.0
        ax.plot(x, d["share"] * 100, color=color, label=f"{lab} (median {summ.loc[g, 'median_dev_ms']:+.1f} ms)")
    ax.axvline(0, color=INK2, lw=0.8)
    ax.text(-1, ax.get_ylim()[1] * 0.97, "late  ", ha="right", va="top", color=INK2, fontsize=9)
    ax.text(1, ax.get_ylim()[1] * 0.97, "  early", ha="left", va="top", color=INK2, fontsize=9)
    ax.set_xlabel("Whiff timing vs. the hitter's own contact point on that pitch type (ms)")
    ax.set_ylabel("Share of whiffs (%)")
    ax.set_title("Late on heat, early on spin")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    _save(fig, out, "fig8_whiff_timing.png", "2024-26 whiffs on competitive swings; 2 ms bins.")


def main(res="results", out="figures"):
    res, out = Path(res), Path(out)
    out.mkdir(exist_ok=True)
    for f in (contact_curves, stabilization, forest, depth_cost, count_mediation, pitch_types, contact_credit,
              whiff_timing):
        f(res, out)
        print("ok", f.__name__)


if __name__ == "__main__":
    main(*sys.argv[1:])
