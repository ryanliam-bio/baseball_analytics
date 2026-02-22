---
draft: true
---

# Bat Speed Analysis Summary

## Data Collection
- **Source:** Statcast via baseballr package
- **Period:** 2025 season (March 18 - September 28)
- **Sample:** ~300k+ swings across 600+ batters
- **Columns:** bat_speed, swing_length, pitch_type, release_speed, balls, strikes, launch_speed, launch_angle, estimated_woba_using_speedangle, and more
- **Note:** SSL/schannel errors required retry logic and `Sys.setenv(CURL_CA_BUNDLE = "")` to resolve

## Key Findings

### 1. Seasonal Percentile Analysis
- **Average bat speed is the most predictive metric** for outcomes (barrel%, exit velo, SLG, xwOBA)
- Impulse (bat_speed^2 / swing_length) does NOT add predictive value beyond raw speed
- Swing length percentiles show weaker correlations than speed (~0.4 vs ~0.7-0.8)
- Contact point (intercept_y_vs_batter) shows almost no correlation with outcomes

**Correlations with outcomes (seasonal):**
| Metric | Barrel% | EV50 | xwOBA |
|--------|---------|------|-------|
| Bat Speed (s50) | 0.72 | 0.87 | 0.45 |
| Swing Length (l50) | 0.41 | 0.43 | 0.18 |
| Impulse (i50) | 0.51 | 0.66 | 0.38 |

### 2. Rolling Analysis (k=50 swings)
- Within-player bat speed fluctuations predict outcome fluctuations
- Correlations strengthen with larger rolling windows (k=30 → k=50 → k=100)
- Optimal window: k=50 balances stability with responsiveness

**Rolling correlations (k=50):**
| Metric | Correlation with Rolling Bat Speed |
|--------|-----------------------------------|
| Rolling Exit Velo | 0.43 |
| Rolling Hard Hit % | 0.47 |
| Rolling xwOBA | 0.25 |

### 3. Bat Speed Stabilization
- **Bat speed stabilizes at ~50 swings** (0.90 correlation with full season)
- This is fast compared to most baseball statistics
- Makes sense: bat speed is mechanical/physical, not outcome-dependent

**By count type:**
- Hitter counts stabilize fastest (~25-30 swings to 0.90)
- Pitcher counts stabilize slowest (~50 swings to 0.90)
- Practical implication: For small samples (spring training), hitter-count bat speed is most reliable

### 4. Count Leverage Effects
**Count classifications:**
- Hitter: 3-0, 3-1, 2-0, 3-2
- Neutral: 2-1, 1-0, 0-0, 1-1
- Pitcher: 0-1, 1-2, 0-2, 2-2

**Rolling correlations with bat speed:**
| Metric | Correlation |
|--------|-------------|
| Pitcher Count % | -0.197 |
| Fastball (FF) % | -0.126 |
| Hitter Count % | +0.089 |

- Pitcher counts hurt bat speed more than hitter counts help
- Being behind in count forces defensive swings with lower bat speed
- Count leverage matters more than pitch type for bat speed

### 5. Pitch Type Effects
- Rolling FF% is weakly negatively correlated with bat speed (-0.126)
- Counterintuitive finding - possible explanations:
  - Hitters sit on fastballs and don't need to swing as hard
  - Offspeed pitches require more aggressive swings to catch up
  - Timing > raw power on fastballs

### 6. Bat Speed Consistency (SD)
- Faster swingers are more consistent (r = -0.45 between speed and SD)
- **Partially a composition effect:** Low-volume role players are both slower AND more variable
- **But real mechanical relationship persists:** Even among regulars (600+ swings), correlation is -0.415

**By swing volume:**
| Volume Tier | Correlation | Avg Speed | Avg SD |
|-------------|-------------|-----------|--------|
| Low (<300) | -0.59 | 68.6 | 9.09 |
| Mid (300-600) | -0.49 | 69.2 | 8.52 |
| High (600+) | -0.42 | 70.0 | 8.00 |

## Methodology Notes
- Non-competitive swings filtered using IQR method (bat_speed < Q1 - 1.5*IQR)
- Minimum 30 swings for player inclusion in percentile analysis
- Hard hit defined as launch_speed >= 95 mph
- Player names reformatted from "Last, First" to "First Last"

## Files Generated
- `bat_speed_impulse_percentiles_filtered.csv` - Player percentile leaderboard
- `bat-tracking-length-correlation.csv` - Seasonal correlation matrix
- `rolling-bat-speed-correlation-count-type.csv` - Rolling correlation matrix with count/pitch type
- `bat-speed-stabilization.png` - Stabilization curve
- `bat-speed-stabilization-by-count.png` - Stabilization by count type
- `soto-rolling-metrics.png` - Example player rolling metrics plot

## Next Steps
- Deeper pitch type analysis (bat speed by pitch type, not just FF%)
- Within-game bat speed trends
- Spring training data comparison once available
- Player-specific case studies (explaining late-season bat speed changes)
