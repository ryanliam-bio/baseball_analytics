# Bat Speed 3.0 — follow-ups (October 2026)

Tests run after 3.0 was published, prompted by Doyoung-Tom Kim (@tomdoyo) on X. He originally asked (June) whether bat acceleration would be more reliable than bat speed, then clarified after 3.0 went up: acceleration over **total swing length**, since swing start point varies much less than contact point.

None of this is on the project page. Every number below comes from `followups.py` (same sample, filters, and contact surfaces as `run_all.py`):

```
python followups.py        # writes results/followups_report.txt and results/followups.json
```

Section references like **§2d** point to sections of `results/followups_report.txt`.

---

## The reply (final draft, 2026-10-05)

> I think the contact point adjustment covers most of that since contact pt alone explains ~86% of the swing-to-swing variation in length, unless I'm misunderstanding. Acceleration using raw numbers took longer to stabilize than bat speed (36 v 20 swings) because the actual acceleration is not constant (typically decreases before a hitter's average contact pt).
>
> CP adjusting speed and length brings acceleration's stabilization down to 20 swings. However, adjusted length/speed (more of a "swing duration" view) is a cleaner look at the same information- it stabilizes in only 14 swings, is almost independent of bat speed where acceleration largely overlaps with it, and tracks a hitter's avg contact depth better than raw length/speed (r=-0.40 v -0.07)

## Figures cited on X

| Claim | Value | What it is exactly | Source |
|---|---|---|---|
| contact pt explains ~86% of swing-to-swing variation in length | 0.858 | Out-of-sample within-hitter R² of the contact surface for swing length (bat speed: 0.275, the page's 27%) | `results/summary.json` → `oos_within_r2.swing_length.inches_full` |
| raw acceleration 36 v bat speed 20 swings | 36.5 v 20.6 | Swings until the first-n average reaches r = .90 with the full-season average (the page's method), 979 hitter-seasons with 400+ swings. Raw acceleration = per-swing v²/L, the page's "impulse" | §1; also `results/extras.json` → `fine_swings_to_r90_full` |
| acceleration typically decreases before a hitter's average contact pt | see §4 table | Local acceleration is at or above the swing's running average for contact 5–15 in out front, 96% of it at 20 in, 86% at 25 in, 76% at the typical 29.7 in, ~0 by 42 in. **Caveat:** inferred from different swings met at different depths, not one swing tracked through time | §4 (controlled) |
| CP-adjusted acceleration: 20 swings | 20.7 | Per-swing v²/L on contact-adjusted speed and length. The page pipeline's surface-fitted `impulse_adj` gives 20.2 | §1; `extras.json` |
| "the same information" | −0.995 / −0.974 | Correlation between adjusted acceleration and adjusted L/v after holding adjusted / raw bat speed fixed (−0.815 with no control). Next-season predictions match to 3 decimals | §2e, §3 |
| adjusted length/speed: 14 swings | 14.0 | Same method as above. 14.9 on the stricter rest-of-season version | §1 |
| almost independent of bat speed | r = −0.16 | Hitter-season adjusted L/v vs adjusted bat speed. Acceleration: +0.70 | §2a |
| tracks avg contact depth: −0.40 v −0.07 | −0.40, −0.07 | Plain correlation with hitter-season average contact depth (ms, + = further out front), adjusted vs raw L/v. Holding bat speed fixed barely changes it: −0.41 (adjusted speed), −0.37 (raw speed) | §2d |

Samples: 923,820 competitive swings; 1,415 hitter-seasons with 150+ swings; 735 consecutive-season pairs; 979 hitter-seasons with 400+ swings for stabilization.

---

## Additional conclusions

### 1. Per-swing vs season-level ratios: no difference
Averaging L/v (or v/L) swing by swing gives the same hitter-season number as dividing season averages: r = 1.000. Per-swing L/v and v/L correlate −0.996. A per-swing median is worse (60 swings to stabilize vs 43). Aggregation choice doesn't matter (§1, §2c).

### 2. Raw vs contact-adjusted is what matters, not the ratio's form
| | Swings to .90 | Year over year | r with depth, holding speed fixed |
|---|---|---|---|
| raw length/speed | 43.3 | .913 | −0.07 |
| raw acceleration | 36.5 | .905 | +0.26 (adj. speed) / +0.05 (raw speed) |
| adjusted length/speed | 14.0 | .916 | −0.41 |
| adjusted acceleration | 20.7 | .913 | +0.42 |

The raw versions carry almost nothing about contact depth. In raw swing length, a compact swing (shorter path) and meeting the ball out front (longer path) pull in opposite directions and cancel. Adjusting length for contact point separates them.

### 3. Constant acceleration doesn't hold, so v²/L overcorrects
Constant acceleration from a fixed start (v² = 2aL) means speed should grow half as fast as path in % terms (elasticity 0.50). On the page's fitted surfaces (controls: hitter-season, count, pitch group, velo), §4:

| Contact depth | Elasticity |
|---|---|
| 12 in behind typical | 0.45 |
| ±6 in around typical (29.7 in) | 0.38 |
| 12 in out front of typical | 0.26 |
| 42 in (bat speed peaks) | ~0 |
| 45+ in | negative (lunging/early swings, per the page) |

Worked example: moving contact from typical to 6 in further out front takes the path from 7.29 to 7.62 ft and speed from 71.3 to 72.4 mph. Constant acceleration would need 72.9 mph, so v²/L drops **1.5%** for the same swing.

Raw bat speed *under*corrects (credits the hitter for out-front contact); v²/L *over*corrects (penalizes it). Because the elasticity changes with depth, no single power of L (v/L^k) can cancel contact point everywhere. That's the case for a fitted model over a formula.

### 4. Adjusted acceleration vs adjusted length/speed: same information, L/v cleaner
- Once bat speed is held fixed they're the same metric, flipped (−0.995 / −0.974).
- Next-season out-of-sample R² is identical (e.g. EV50 .6136 vs .6141 alongside adjusted speed). Using both is slightly worse.
- L/v stabilizes faster (14.0 vs 20.7 swings). The square on v adds noise: v/L *without* the square takes 13.3.
- L/v's depth correlation doesn't depend on which bat speed you hold fixed (−0.40 / −0.41 / −0.37). Acceleration's does (+0.27 plain / +0.42 / +0.20), because half of it is bat speed.
- Acceleration on its own is far weaker than raw speed on its own (next-season EV50 R² .41 vs .62).

### 5. Why length/speed is nearly independent of speed (not by construction)
Across hitters, path length scales like speed^0.80 (r = +0.55), close to proportional, so length per mph comes out flat across bat speeds. Dividing doesn't guarantee that: v²/L also divides and correlates +0.70. The depth link holds within every speed tier: −0.34 (slowest third), −0.44 (middle), −0.45 (fastest) (§2f).

### 6. Predictive value: none beyond raw bat speed
Raw speed + depth + adjusted L/v vs raw speed alone. Next-season out-of-sample R² gain, 95% CI from resampling batters (§3):

| | barrel | EV50 | hard-hit | xwOBAcon | whiff |
|---|---|---|---|---|---|
| gain | −.004 | +.007 | +.007 | +.013 | +.001 |
| 95% CI | [−.006, −.002] | [−.002, +.016] | [−.006, +.020] | [−.003, +.028] | [−.010, +.012] |

None of the positive gains is distinguishable from zero; barrel gets slightly worse. Adjusted L/v isn't just contact depth in disguise (next-season EV50 partial −0.22 → −0.15 after also controlling depth), but its value is **descriptive** (swing shape; explains why hitters have the contact points they do), not projection.

For contrast, the page's "adjusted + next year's contact point credit" row **does** beat raw speed significantly: barrel +.017 [.005, .031], EV50 +.013 [.004, .022], hard-hit +.011 [.001, .020], xwOBAcon +.009 [.000, .017]; whiff a tie. The page's claim holds.

### 7. Bat speed and contact depth
Hitter-season average contact depth vs bat speed: raw +0.19, adjusted −0.04. Raw speed includes the contact credit, so out-front hitters show a little more of it.

### 8. A-swing / B-swing
- **The IQR filter isn't hiding B swings.** Its floor sits 12.6 mph below the hitter's median.
- **Bat speed distributions don't show two humps**, but that test can't see realistic B swings. Clearly bimodal: 0.5% of hitter-seasons (adjusted), 5.5% (raw). Power check: with the observed 3.65 mph within-hitter SD, a planted B swing is detected 2% of the time at 5 mph slower and 97% at 6 mph. The real two-strike drop is ~1.2 mph.
- **Labeled by count, the two-strike swing is a real, stable trait.** Within hitter, controlling pitch group and velo: −1.79 mph raw, −1.20 mph at the same contact point, 1.16 ms deeper, path at the same contact point essentially unchanged (−0.08 ft). Between-hitter SD 0.65 mph, reliability 0.80, year over year 0.73 (depth shift: 0.71).
- **Mostly speed-driven, not contact-point-driven.** Across hitters, the raw drop tracks the same-contact-point drop (+0.91) more than the depth shift (+0.50); the two parts are only loosely related (+0.19).
- **It buys contact at no visible cost.** Backing off more → fewer two-strike whiffs: +0.31 same season (effect estimated on contact swings only, so whiffs can't feed their own predictor), +0.21 next season, controlling <2-strike whiff rate and bat speed. Going deeper: +0.22 / +0.16. Cost vs EV50 −0.04, xwOBAcon −0.01.
- **Leaderboard** (2024–26, 1,000+ contact swings, n = 290). Backs off most: Giménez, Caballero, Schanuel, Jeffers, Paredes, Soto. Barely backs off: Lenyn Sosa, Triolo, Montgomery, Marsh. Goes deepest: Trea Turner, Bichette, Paredes, Dominic Smith, Hoerner.

---

## Clarifications made along the way (don't repeat these)
- "86% of swing length" is wrong. It's 86% of the swing-to-swing *variation* in a hitter's swing length.
- The impulse vs L/v difference isn't about scaling. Raw versions of both are empty; adjusted versions of both carry the same signal. The contact adjustment is what matters.
- An uncontrolled within-hitter regression gave elasticities of 0.27 (typical) and 0.02 (out front). Those are **confounded**: out-front contact over-represents offspeed, where hitters swing softer. Use the controlled numbers (0.38 / 0.26).
- The worked example is −1.5% (exact, from the reference depth). Earlier drafts said −2.7% (uncontrolled) and −1.8% (read off the table).
- Signs: adjusted L/v vs depth is negative (−0.40); adjusted acceleration vs depth is positive. Don't write "both r = −0.41".
- "Controlling for bat speed": say which. It matters for acceleration (+0.42 vs +0.20), not for L/v.
- Length/speed is a *cleaner* version of the same information as acceleration, not *more informative*.
- Don't mix stabilization methods in one sentence: full-season (page: 20 / 14 / 36) vs rest-of-season (page's stabilization figure: ~24 / ~15).
- The adjusted acceleration's 20 swings is for v²/L. Plain v/L stabilizes like L/v (13.3).

## Page edits suggested, not yet made
1. **Acceleration section:** say the length/speed numbers are contact-adjusted and the raw ratio carries none of it (depth −0.07; whiff +0.12 raw vs −0.02 adjusted). Only the first bullet currently says "contact-adjusted".
2. **Quantify "(flawed) assumption of constant acceleration"** with the elasticity sentence from §3 above.
3. **Qualify "go with slightly more damage the following year (EV50, r = −0.22)":** it doesn't improve on raw bat speed for projecting next season (§6 above).
4. *Optional:* a short two-strike-swing paragraph in the counts section, with the bimodality null as an avenue explored.

Withdrawn: adding "(−0.15 even after controlling for contact depth)" to the EV50 claim. The correlation is real, but it overstates projection value.

## Definitions
- **Adjusted** = contact-point-adjusted with the page's within-hitter contact surfaces (`evaluate.add_adjusted_columns`). Not adjusted for bat speed.
- **Length/speed (L/v)** = season-average swing length ÷ season-average bat speed (`evaluate.hitter_table` → `length_per_mph`).
- **Acceleration** = per-swing v²/L, averaged. Same as the page's "impulse"; twice the average acceleration under constant acceleration (v²/2L).
- **Contact depth** = `depth_ms`, contact point in front of the hitter's center of mass, converted to milliseconds of ball travel.
