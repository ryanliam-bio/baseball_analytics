---
title: "Addison Barger: &#36;50m of Surplus Value"
summary: "A scenario-weighted surplus value model for Addison Barger's four remaining control years with the Blue Jays (2027-30)."
date: "2026-10-22"
tags:
  - Python
  - Surplus Value
  - Statcast
share: false
profile: false
math: false
build:
  list: never
---

> [!abstract] Summary
> Addison Barger will generate &#36;50m in surplus value for the Blue Jays. He's accrued 1.9 fWAR in three seasons,
> but Toronto controls him through 2030 (his age-30 season) at pre-arb and arbitration prices. Four weighted
> scenarios, priced at FanGraphs' 2026 free-agent rates, give an **expected surplus of &#36;61m** and a **44% chance
> of clearing &#36;50m**. A 3+ WAR breakout carries 55% of the value.

This page backs up my player evaluation for the Tigers 2026 analyst questionnaire. It shows how the dollars were built and where every number in the written answer comes from ([below](#every-number-in-the-write-up)).

## Scenarios

| Scenario | Weight | wRC+ | Basis |
|---|---|---|---|
| Bust | 15% | 85 | Elbow or back problems recur; part-timer, non-tendered after 2028 |
| Platoon | 30% | 108 | Strong side only (115 wRC+ vs. RHP in 2025, regressed) |
| 2025 repeat | 35% | 107 | 2025 again, with a normal platoon split |
| Breakout | 20% | 130 | Chase gains stick: about .370 xwOBA, the median for fast swingers with sub-27% chase |

**Plate appearances and salary by season**

| Scenario | 2027 | 2028 | 2029 | 2030 |
|---|---|---|---|---|
| Bust | 250 PA, &#36;0.85m | 200 PA, &#36;1.2m | Non-tendered | |
| Platoon | 350 PA, &#36;0.85m | 400 PA, &#36;1.5m | 400 PA, &#36;2.5m | 400 PA, &#36;3.5m |
| 2025 repeat | 450 PA, &#36;0.85m | 575 PA, &#36;2.5m | 575 PA, &#36;4.5m | 575 PA, &#36;7.0m |
| Breakout | 500 PA, &#36;0.85m | 625 PA, &#36;4.0m | 625 PA, &#36;9.0m | 625 PA, &#36;14.0m |

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

- **Market value:** the league minimum (&#36;0.8m) plus WAR x &#36;/WAR. The rates come from Ben Clemens's 2026 free-agent study: **&#36;6.74m / &#36;8.51m / &#36;12.84m per WAR** for players projected at 0-1 / 1-2 / 2+ WAR, in 2025 dollars.
- **Inflation:** market value grows 5% a year.
- **Surplus:** market value minus salary, discounted 5% a year to 2027.
- **Non-tender:** arbitration years work like team options, which is what limits the bust case's losses.

## Results

| Scenario | Weight | WAR, arm intact / lost | Salary | Surplus, arm intact / lost |
|---|---|---|---|---|
| Bust | 15% | -0.2 | &#36;2.0m | -&#36;2m |
| Platoon | 30% | 5.1 / 3.5 | &#36;8.3m | &#36;44m / &#36;22m |
| 2025 repeat | 35% | 6.9 / 4.7 | &#36;14.8m | &#36;55m / &#36;32m |
| Breakout | 20% | 14.2 / 11.7 | &#36;27.9m | &#36;179m / &#36;144m |
| **Expected** | | | | **&#36;61m** |

Every outcome, with its probability:

| Surplus | Probability | Outcome |
|---|---|---|
| -&#36;2m | 15.0% | Bust |
| &#36;22m | 9.0% | Platoon, arm lost |
| &#36;32m | 10.5% | 2025 repeat, arm lost |
| &#36;44m | 21.0% | Platoon, arm intact |
| &#36;55m | 24.5% | 2025 repeat, arm intact |
| &#36;144m | 6.0% | Breakout, arm lost |
| &#36;179m | 14.0% | Breakout, arm intact |

- **Mean:** &#36;61m. **Median:** &#36;44m. **P(≥&#36;50m):** 44%.
- **Concentration:** the breakout supplies 55% of the expected value. In that case he produces 13.4 WAR for &#36;27.9m, about &#36;2.1m per win.

## Sensitivity

**Expected surplus (&#36;m) by breakout probability and pricing.** The breakout probability is moved to or from the 2025-repeat case.

| P(breakout) | Tiered &#36;/WAR | One rate (&#36;11.23m) |
|---|---|---|
| 5% | 43.0 | 56.0 |
| 10% | 49.1 | 59.9 |
| 20% | 61.2 | 67.7 |
| 30% | 73.3 | 75.5 |

**Arm survival:**

| P(arm intact) | Expected surplus |
|---|---|
| 40% | &#36;54.7m |
| 70% (base) | &#36;61.2m |
| 90% | &#36;65.5m |

**Arbitration salaries, scaled across 2028-30:**

| Multiplier | Mean | Median | P(≥&#36;50m) |
|---|---|---|---|
| 0.75x | &#36;64.0m | &#36;45.2m | 44% |
| 1.00x | &#36;61.2m | &#36;43.5m | 44% |
| 1.25x | &#36;58.3m | &#36;41.8m | 44% |
| 1.50x | &#36;55.5m | &#36;40.2m | 20% |
| 2.00x | &#36;49.8m | &#36;36.8m | 20% |

**Pessimistic weights** (bust 30%, platoon 35%, repeat 20%, breakout 15%, arm 50%): **&#36;43.6m expected, 25% chance of clearing &#36;50m.**

## Limitations

- **The &#36;50m line sits close to the 44%.** A quarter of the probability (2025 repeat, arm intact) clears it by under &#36;5m. Arbitration awards 50% higher drop that case below the line, and P(≥&#36;50m) falls to 20%.
- **The weights are judgment, not fitted.** Each scenario's wRC+ is anchored to a 2025 split or a comparison group. How often each happens is my read.
- **One full season.** 2025 is his only full MLB season, and he played 28 games in 2026 before surgery.

## Every number in the write-up

Unless noted, percentiles are among 2025 MLB regular-season hitters with 300+ PA, computed as rank / n with the hitter included (the way Orr's app displays them). The § numbers refer to sections of `supporting_calcs.py`.

| Claim | Value | Source and method |
|---|---|---|
| 1.9 fWAR in three years; 107 wRC+; 24.1% K% | | [FanGraphs](https://www.fangraphs.com/players/addison-barger/24598/stats) |
| Control through age 30 | Free agent after 2030 | FanGraphs service time (1.103 entering 2026); born Nov. 12, 1999 |
| Contact point, 6th to 60th percentile | 25.1 to 31.6 in out front | Savant [Swing Path / Attack Angle](https://baseballsavant.mlb.com/leaderboard/bat-tracking/swing-path-attack-angle), contact depth vs. batter, 2024 vs. 2025, 300+ competitive swings (§1) |
| Bat speed 75.9 mph | 74.4 mph (87th pct) in 2024, 75.9 (94th) in 2025 | Same leaderboard (§1) |
| Hard-hit rate 38% to 51% | 38.3% to 51.0% | Savant [custom leaderboard](https://baseballsavant.mlb.com/leaderboard/custom), EV 95+ mph (§2) |
| 83rd-percentile damage rate, 67th-percentile SEAGER | | Robert Orr's Hitter Percentiles app, MLB 2025 regular season, 300+ PA. Data: [Py-Damage](https://github.com/notthebobbyorr/Py-Damage). SEAGER: [Orr, Baseball Prospectus](https://www.baseballprospectus.com/news/article/86572/the-crooked-inning-corey-seager-rangers/) |
| Worse-than-average chase and whiff | Chase 31.0% (median 27.7%), whiff 26.1% (median 24.4%) | Savant custom leaderboard (§3) |
| Chase of 21% in April, 42% in July, 25% in September | | FanGraphs monthly splits, O-Swing% |
| Sub-27% chase: .372 vs. .326 median xwOBA | 7 vs. 26 hitters | Savant custom leaderboard, 2025, 300+ PA (§4). Group: bat speed at or above the 85th percentile and squared-up per swing at or below the 35th (n=33, Barger included). Under 27% chase: Judge, Schwarber, Acuña, Kurtz, Chapman, Wood, Baty |
| 13% of fastballs in play popped up (96th percentile) | 25 of 192; median 6.8% | Statcast Search, four-seamers/sinkers/cutters, popups per batted ball (§5) |
| 99th-percentile arm | 96.5 mph, 3rd of 395 | Savant [Arm Strength](https://baseballsavant.mlb.com/leaderboard/arm-strength), 2025, 50+ throws (§6) |
| .828 AAA OPS vs. lefties | 2023-24, 170 PA (.369 BABIP) | MLB Stats API / [MiLB.com](https://www.milb.com/player/addison-barger-680718) splits |
| Okamoto keeping 3B; elbow surgery | | MLB.com: [Okamoto signing](https://www.mlb.com/news/kazuma-okamoto-blue-jays-deal), [Barger surgery](https://www.mlb.com/news/addison-barger-elbow-surgery-blue-jays) |
| &#36;61m expected; P(≥&#36;50m) 44%; breakout over half | | `barger_surplus.py`, above |

## Code

- [`code/barger_surplus.py`](code/barger_surplus.py) reproduces every number in the surplus model. It needs only numpy, with no data downloads.
- [`code/supporting_calcs.py`](code/supporting_calcs.py) rebuilds the Statcast numbers in the table above from public Savant endpoints. It needs pandas and takes about a minute.

```
python barger_surplus.py
python supporting_calcs.py
```

## Sources

- Ben Clemens, ["What Are Teams Paying For A Win In Free Agency? 2026 Edition,"](https://blogs.fangraphs.com/what-are-teams-paying-for-a-win-in-free-agency-2026-edition/) FanGraphs, Feb. 24, 2026
- [FanGraphs WAR framework](https://library.fangraphs.com/misc/war/)
- [FanGraphs](https://www.fangraphs.com/players/addison-barger/24598/stats): fWAR, wRC+, platoon splits, service time
- [Baseball Savant](https://baseballsavant.mlb.com/savant-player/addison-barger-680718): arm strength, Statcast batting data
- Robert Orr's SEAGER and damage data: [github.com/notthebobbyorr/Py-Damage](https://github.com/notthebobbyorr/Py-Damage)
- MLB.com: [Barger elbow surgery](https://www.mlb.com/news/addison-barger-elbow-surgery-blue-jays), [Okamoto signing](https://www.mlb.com/news/kazuma-okamoto-blue-jays-deal)
