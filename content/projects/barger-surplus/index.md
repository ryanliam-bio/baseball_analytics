---
title: "Addison Barger: $50m of Surplus Value"
summary: "A scenario-weighted surplus value model for Addison Barger's four remaining control years with the Blue Jays (2027-30)."
date: "2026-10-22"
tags:
  - Python
  - Surplus Value
  - Statcast
share: false
profile: false
math: false
weight: 1
---

> [!abstract] Summary
> Addison Barger will generate $50m in surplus value for the Blue Jays. He's accrued 1.9 fWAR in three seasons,
> but Toronto controls him through 2030 (his age-30 season) at pre-arb and arbitration prices. Four weighted
> scenarios, priced at FanGraphs' 2026 free-agent rates, give an **expected surplus of $61m** and a **44% chance
> of clearing $50m**. A 3+ WAR breakout carries 55% of the value.

This page backs up the pricing behind my player evaluation for the Tigers 2026 analyst questionnaire. The scouting case (contact point, chase, popups) is in the written answer; this page covers how the dollars were built.

## Scenarios

| Scenario | Weight | wRC+ | PA, 2027-30 | Salary, 2027-30 ($m) | Basis |
|---|---|---|---|---|---|
| Bust | 15% | 85 | 250, 200, 0, 0 | 0.85, 1.2, non-tendered | Elbow or back problems recur; part-timer, non-tendered after 2028 |
| Platoon | 30% | 108 | 350, 400, 400, 400 | 0.85, 1.5, 2.5, 3.5 | Strong side only (115 wRC+ vs. RHP in 2025, regressed) |
| 2025 repeat | 35% | 107 | 450, 575, 575, 575 | 0.85, 2.5, 4.5, 7.0 | 2025 again, with a normal platoon split |
| Breakout | 20% | 130 | 500, 625, 625, 625 | 0.85, 4.0, 9.0, 14.0 | Chase gains stick: about .370 xwOBA, the median for fast swingers with sub-27% chase |

The weights and salaries are my judgment calls. 2027 is his last pre-arb season. The arbitration salaries are assumptions, and the sensitivity tables below vary them.

## From runs to WAR

FanGraphs-style, per 600 PA:

- **Batting runs:** (wRC+ - 100) / 100 x 0.118 runs per PA x 600.
- **Baserunning:** -2 runs (his 2025 BsR ran about -2 to -3).
- **Position:** -7.5 runs for right field. With Okamoto at third base, Barger is modeled as a right fielder.
- **Fielding:** +3 runs if his arm survives the 2026 elbow surgery (99th-percentile arm strength in 2025), -3 if it doesn't. The arm survives in 70% of non-bust outcomes; the bust case assumes it didn't.
- **Replacement level:** +20 runs.
- **Runs per win:** 9.7.

## From WAR to dollars

- **Market value:** the league minimum ($0.8m) plus WAR x $/WAR. The rates come from Ben Clemens's 2026 free-agent study: **$6.74m / $8.51m / $12.84m per WAR** for players projected at 0-1 / 1-2 / 2+ WAR, in 2025 dollars.
- **Inflation:** market value grows 5% a year.
- **Surplus:** market value minus salary, discounted 5% a year to 2027.
- **Non-tender:** arbitration years work like team options, which is what limits the bust case's losses.

## Results

| Scenario | Weight | WAR, arm intact / lost | Salary | Surplus, arm intact / lost |
|---|---|---|---|---|
| Bust | 15% | -0.2 | $2.0m | -$2m |
| Platoon | 30% | 5.1 / 3.5 | $8.3m | $44m / $22m |
| 2025 repeat | 35% | 6.9 / 4.7 | $14.8m | $55m / $32m |
| Breakout | 20% | 14.2 / 11.7 | $27.9m | $179m / $144m |
| **Expected** | | | | **$61m** |

Every outcome, with its probability:

| Surplus | Probability | Outcome |
|---|---|---|
| -$2m | 15.0% | Bust |
| $22m | 9.0% | Platoon, arm lost |
| $32m | 10.5% | 2025 repeat, arm lost |
| $44m | 21.0% | Platoon, arm intact |
| $55m | 24.5% | 2025 repeat, arm intact |
| $144m | 6.0% | Breakout, arm lost |
| $179m | 14.0% | Breakout, arm intact |

- **Mean:** $61m. **Median:** $44m. **P(≥$50m):** 44%.
- **Concentration:** the breakout supplies 55% of the expected value. In that case he produces 13.4 WAR for $27.9m, about $2.1m per win.

## Sensitivity

**Expected surplus ($m) by breakout probability and pricing.** The breakout probability is moved to or from the 2025-repeat case.

| P(breakout) | Tiered $/WAR | One rate ($11.23m) |
|---|---|---|
| 5% | 43.0 | 56.0 |
| 10% | 49.1 | 59.9 |
| 20% | 61.2 | 67.7 |
| 30% | 73.3 | 75.5 |

**Arm survival:**

| P(arm intact) | Expected surplus |
|---|---|
| 40% | $54.7m |
| 70% (base) | $61.2m |
| 90% | $65.5m |

**Arbitration salaries, scaled across 2028-30:**

| Multiplier | Mean | Median | P(≥$50m) |
|---|---|---|---|
| 0.75x | $64.0m | $45.2m | 44% |
| 1.00x | $61.2m | $43.5m | 44% |
| 1.25x | $58.3m | $41.8m | 44% |
| 1.50x | $55.5m | $40.2m | 20% |
| 2.00x | $49.8m | $36.8m | 20% |

**Pessimistic weights** (bust 30%, platoon 35%, repeat 20%, breakout 15%, arm 50%): **$43.6m expected, 25% chance of clearing $50m.**

## Limitations

- **The $50m line sits close to the 44%.** A quarter of the probability (2025 repeat, arm intact) clears it by under $5m. Arbitration awards 50% higher drop that case below the line, and P(≥$50m) falls to 20%.
- **The weights are judgment, not fitted.** Each scenario's wRC+ is anchored to a 2025 split or a comparison group. How often each happens is my read.
- **One full season.** 2025 is his only full MLB season, and he played 28 games in 2026 before surgery.

## Code

[`code/barger_surplus.py`](code/barger_surplus.py) reproduces every number on this page. It needs only numpy, with no data downloads:

```
python barger_surplus.py
```

## Sources

- Ben Clemens, ["What Are Teams Paying For A Win In Free Agency? 2026 Edition,"](https://blogs.fangraphs.com/what-are-teams-paying-for-a-win-in-free-agency-2026-edition/) FanGraphs, Feb. 24, 2026
- [FanGraphs WAR framework](https://library.fangraphs.com/misc/war/)
- [FanGraphs](https://www.fangraphs.com/players/addison-barger/24598/stats): fWAR, wRC+, platoon splits, service time
- [Baseball Savant](https://baseballsavant.mlb.com/savant-player/addison-barger-680718): arm strength, Statcast batting data
- Robert Orr's SEAGER and damage data: [github.com/notthebobbyorr/Py-Damage](https://github.com/notthebobbyorr/Py-Damage)
- MLB.com: [Barger elbow surgery](https://www.mlb.com/news/addison-barger-elbow-surgery-blue-jays), [Okamoto signing](https://www.mlb.com/news/kazuma-okamoto-blue-jays-deal)
