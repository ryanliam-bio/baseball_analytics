"""Rough surplus value for Addison Barger's remaining control years (2027 pre-arb, 2028-30 arb).
Run: python barger_surplus.py  (needs numpy)

Every number below is an assumption, chosen to be argued with. WAR is built FanGraphs-style from runs:
batting (from wRC+) + baserunning + fielding + positional + replacement, divided by runs per win.
With Okamoto at 3B, Barger is modeled as a right fielder. Whether his arm survives the elbow repair is a
separate coin (ARM_OK) that sets his fielding runs; the bust case assumes it didn't.

Market value follows Ben Clemens, "What Are Teams Paying For A Win In Free Agency? 2026 Edition"
(FanGraphs, Feb 24 2026): league minimum + WAR x $/WAR, in 2025 dollars, inflated 5%/yr. The 2025-26
market paid $6.74M/WAR to players projected 0-1 WAR, $8.51M for 1-2, $12.84M for 2+ ($11.23M one-tier).
Surplus = market value - salary, discounted to 2027. Arb years are effectively team options (non-tender),
which is what caps the bust case.
"""
import numpy as np

YEARS = [2027, 2028, 2029, 2030]
TIERS = [(1.0, 6.74), (2.0, 8.51), (np.inf, 12.84)]   # (WAR upper bound, $M per WAR, 2025 dollars)
ONE_TIER = 11.23
INFLATION, DISCOUNT, LEAGUE_MIN = 0.05, 0.05, 0.8    # Clemens inflates at 5%; min in $M
RUNS_PER_WIN, LG_RUNS_PER_PA = 9.7, 0.118
REPLACEMENT, BASERUNNING = 20.0, -2.0          # runs per 600 PA (2025 BsR about -2 to -3)
POSITION = {"3B": 2.5, "RF": -7.5, "DH": -17.5}  # runs per 600 PA
ARM_OK = 0.70                                   # P(arm strength survives the elbow repair)
FIELDING = {True: 3.0, False: -3.0}             # RF runs per 600: 2025 arm +4 with some range give-back

# name: (probability, PA by year, wRC+, position, salary $M by year, rationale)
SCENARIOS = {
    "bust": (0.15, [250, 200, 0, 0], 85, "RF", [0.85, 1.2, 0, 0],
             "elbow/back recur; part-timer, non-tendered after 2028"),
    "platoon floor": (0.30, [350, 400, 400, 400], 108, "RF", [0.85, 1.5, 2.5, 3.5],
                      "strong side only; 115 wRC+ vs RHP in 2025, regressed"),
    "median": (0.35, [450, 575, 575, 575], 107, "RF", [0.85, 2.5, 4.5, 7.0],
               "2025 again (107 wRC+) with a normal platoon split"),
    "tail": (0.20, [500, 625, 625, 625], 130, "RF", [0.85, 4.0, 9.0, 14.0],
             "chase drop sticks: ~.370 xwOBA (low-chase archetype median), everyday RF"),
}


def war(pa, wrc, pos, arm_ok):
    per600 = ((wrc - 100) / 100 * LG_RUNS_PER_PA * 600 + BASERUNNING + FIELDING[arm_ok]
              + POSITION[pos] + REPLACEMENT)
    return np.array(pa) / 600 * per600 / RUNS_PER_WIN


def rate(w, flat=None):
    """$M per WAR in 2025 dollars: Clemens's tier for a season of w WAR, or a flat rate."""
    return flat if flat is not None else next(r for cap, r in TIERS if w < cap)


def surplus(w, salary, flat=None):
    t = np.arange(len(YEARS))
    infl = (1 + INFLATION) ** (t + 2)              # 2025 dollars -> 2027 onward
    played = np.array(salary) > 0
    value = np.where(played, LEAGUE_MIN * infl / (1 + INFLATION) ** 2 + np.array([rate(x, flat) for x in w]) * w * infl, 0)
    return float(((value - np.array(salary)) * (1 + DISCOUNT) ** -t).sum())


def expected(probs, flat=None, arm_ok=ARM_OK):
    total = 0.0
    for name, (_, pa, wrc, pos, sal, _) in SCENARIOS.items():
        p_arm = 0.0 if name == "bust" else arm_ok
        for ok, p in ((True, p_arm), (False, 1 - p_arm)):
            total += probs[name] * p * surplus(war(pa, wrc, pos, ok), sal, flat)
    return total


base = {k: v[0] for k, v in SCENARIOS.items()}
assert abs(sum(base.values()) - 1) < 1e-9
print(f"Clemens tiered $/WAR (2025 $, +{INFLATION:.0%}/yr), {DISCOUNT:.0%} discount; RF; P(arm intact) {ARM_OK:.0%}\n")
print(f"{'scenario':14s} {'P':>4s} {'WAR arm ok/lost':>16s} {'salary':>7s} {'surplus ok/lost':>16s}  rationale")
for name, (p, pa, wrc, pos, sal, why) in SCENARIOS.items():
    w_ok, w_lost = war(pa, wrc, pos, True), war(pa, wrc, pos, False)
    print(f"{name:14s} {p:4.0%} {w_ok.sum():7.1f} / {w_lost.sum():4.1f}  {sum(sal):7.1f} "
          f"{surplus(w_ok, sal):7.1f} / {surplus(w_lost, sal):5.1f}  {why}")

ev = expected(base)
tail_only = {k: (v if k == "tail" else 0) for k, v in base.items()}
print(f"\nexpected surplus ${ev:.1f}M; tail share {expected(tail_only) / ev:.0%}")
_, pa, wrc, pos, sal, _ = SCENARIOS["tail"]
w_tail = ARM_OK * war(pa, wrc, pos, True) + (1 - ARM_OK) * war(pa, wrc, pos, False)
print(f"tail: {w_tail.sum():.1f} WAR for ${sum(sal):.1f}M (${sum(sal) / w_tail.sum():.1f}M per WAR)")

cols = [("tiered", None), ("$11.23M", ONE_TIER), ("$8.1M", 8.1)]
print("\nexpected surplus ($M) by P(tail) (difference taken from 'median') and pricing (2025 $)")
print(f"{'P(tail)':>8s}" + "".join(f"{c:>9s}" for c, _ in cols))
for pt in (0.05, 0.10, 0.20, 0.30):
    probs = dict(base, median=base["median"] + base["tail"] - pt, tail=pt)
    print(f"{pt:8.0%}" + "".join(f"{expected(probs, f):9.1f}" for _, f in cols))

print("\nby P(arm intact):", ", ".join(f"{a:.0%} -> ${expected(base, arm_ok=a):.1f}M" for a in (0.4, 0.7, 0.9)))
pess = {"bust": 0.30, "platoon floor": 0.35, "median": 0.20, "tail": 0.15}
print(f"pessimistic weights {pess}, arm 50%: ${expected(pess, arm_ok=0.5):.1f}M")


# How likely is "$50M of surplus"? Probability-weighted outcome table (scenario x arm)
def outcomes(probs, flat=None, arm_ok=ARM_OK):
    rows = []
    for name, (_, pa, wrc, pos, sal, _) in SCENARIOS.items():
        p_arm = 0.0 if name == "bust" else arm_ok
        for ok, p in ((True, p_arm), (False, 1 - p_arm)):
            if probs[name] * p > 0:
                rows.append((surplus(war(pa, wrc, pos, ok), sal, flat), probs[name] * p, f"{name}, arm {'ok' if ok else 'lost'}"))
    return sorted(rows)


def p_at_least(target, probs, **kw):
    return sum(p for v, p, _ in outcomes(probs, **kw) if v >= target)


def median_outcome(probs, **kw):
    cum = 0
    for v, p, _ in outcomes(probs, **kw):
        cum += p
        if cum >= 0.5:
            return v


print("\noutcomes (surplus $M, probability):")
for v, p, lab in outcomes(base):
    print(f"   {v:7.1f}  {p:5.1%}  {lab}")
print(f"P(surplus >= $50M): {p_at_least(50, base):.0%}; median outcome ${median_outcome(base):.1f}M; mean ${expected(base):.1f}M")
for lab, kw in [("one-tier $11.23M", {"flat": ONE_TIER}), ("flat $8.1M", {"flat": 8.1})]:
    print(f"   {lab}: P(>= $50M) {p_at_least(50, base, **kw):.0%}, mean ${expected(base, **kw):.1f}M")
print(f"   pessimistic weights, arm 50%: P(>= $50M) {p_at_least(50, pess, arm_ok=0.5):.0%}")

# Arbitration sensitivity: scale the 2028-30 arb salaries in every scenario (2027 pre-arb unchanged)
print("\narb salary multiplier -> mean, median, P(>= $50M)  [scenario arb totals 2028-30 at 1.0x: "
      + ", ".join(f"{n} ${sum(v[4][1:]):.1f}M" for n, v in SCENARIOS.items()) + "]")
_orig = SCENARIOS
for k in (0.75, 1.0, 1.25, 1.5, 2.0):
    SCENARIOS = {n: (p, pa, w, pos, [s[0]] + [x * k for x in s[1:]], why) for n, (p, pa, w, pos, s, why) in _orig.items()}
    med_ok = [v for v, _, lab in outcomes(base) if lab == "median, arm ok"][0]
    print(f"   {k:4.2f}x  mean ${expected(base):5.1f}M  median ${median_outcome(base):5.1f}M  "
          f"P(>=50) {p_at_least(50, base):.0%}  (median-scenario, arm ok: ${med_ok:.1f}M)")
SCENARIOS = _orig
