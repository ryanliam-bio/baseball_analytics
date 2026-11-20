# Bat Speed 3.0 — contact-point-adjusted bat tracking

Pipeline behind the 2024–26 contact-point analysis. Python 3.10+, pandas, numpy, scikit-learn, matplotlib, pyarrow.

## Run

```
python savant_swings.py                 # pull swings (see that script's docstring)
python run_all.py --data savant_out/swings_2024.parquet savant_out/swings_2025.parquet savant_out/swings_2026.parquet
python extras.py                        # follow-ups (timing shift, profile models, leaderboards, fine stabilization)
python whiff_timing.py                  # whiff timing by pitch group
python figures.py results figures       # PNGs
python verify.py                        # independent re-derivation of headline numbers
python count_tango.py                   # count effects using 2.0's Tango count buckets + depth-cost split
python verify_2_0.py swings_df_backup.rds   # reproduces the Bat Speed 2.0 corrections
python run_all.py --simulate            # pipeline test on synthetic swings with planted effects
```

`run_all.py` and `extras.py` expect the parquet files in `data/` (edit `DATA` in extras.py / whiff_timing.py / verify.py if yours live elsewhere). Full run ≈ 12 minutes on a laptop.

## Method in one paragraph

Competitive swings (2.0's IQR rule per hitter-season, bunts out) get a contact surface fit *within hitter-season*: bat speed = hitter-season fixed effect + f(depth, distance off body, zone-relative height) + count, pitch group and pitch speed terms. f is cubic B-spline main effects plus pairwise tensor interactions. A swing's contact-adjusted value is its raw value minus (f at its contact point − league-average f), so adjusted and raw share the same league mean and the difference reads as "mph his contact point is worth". Same machinery for swing length and impulse. Depth in milliseconds uses the ball's y-velocity at the front of the plate from the Statcast trajectory (vy0, ay).

## Files

| file | what |
|---|---|
| `prep.py` | filters, derived features (depth, off-body, height, depth in ms, pitch groups, counts), hitter-season outcomes, data-quality checks |
| `contact_model.py` | spline surface, within vs pooled fits, adjustment, out-of-sample within-hitter R² |
| `evaluate.py` | hitter table, stabilization, split-half, year-over-year, same/next-season correlations, cluster bootstrap |
| `tradeoff.py` | per-hitter depth sensitivity (mph per inch / per ms), empirical-Bayes shrinkage |
| `context.py` | count and pitch-type mediation (total vs same-contact-point), timing shift, whiff anatomy |
| `simulate.py` | synthetic swings with known effects for testing |
| `results/` | every table behind the write-up (`summary.json`, `extras.json`, CSVs) |
| `figures/` | fig1–fig8 |

## Definitions worth knowing

- **Depth**: `intercept_ball_minus_batter_pos_y_inches`, + = in front of the hitter's center of mass. **Off body**: `..._x_inches` (already batter-relative).
- **Outcomes** come from swings only, so xwOBA is xwOBAcon (no walks / called Ks). Whiff = swinging_strike(+_blocked); foul tips count as contact.
- **Stabilization**: first n swings vs the mean of all *later* swings that season (no overlap), hitters with 400+ swings. Not directly comparable to 2.0's rolling-window figure.
- **Next season**: season-s metric vs season s+1 outcome, hitters with 150+ competitive swings in both.
- **Timing shift**: mean depth (ms) on breaking / offspeed minus fastballs, contact swings only (fouls + balls in play) so whiffs can't feed their own predictor.
