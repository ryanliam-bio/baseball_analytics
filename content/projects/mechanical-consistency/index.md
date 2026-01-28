---
title: "Mechanical Consistency Profiling"
summary: "SQL-driven analysis of pitching biomechanics using the Driveline OpenBiomechanics dataset to quantify repeatability and its relationship to velocity."
tags:
  - SQL
  - Biomechanics
  - Driveline
  - Featured
date: "2026-01-27"
share: false
profile: false
draft: true
weight: 3
image:
  filename: "consistency_scatter.png"
  caption: "Velocity vs Mechanical Consistency"
  focal_point: "Smart"
  preview_only: false
---

<a href="analysis_queries.sql" download class="btn btn-primary">
📥 Download SQL Queries
</a>
<a href="setup_database.R" download class="btn btn-outline-primary">
📥 Download R Setup Script
</a>

---

### Motivation

"Repeatability" is a frequent topic in pitching development conversations, but it's rarely quantified rigorously. This project uses the [Driveline OpenBiomechanics Project](https://github.com/drivelineresearch/openbiomechanics) dataset to answer:

1. **How consistent are elite pitchers mechanically?**
2. **Do higher-velocity pitchers exhibit more or less variability?**
3. **Which biomechanical metrics show the tightest consistency?**

This analysis focuses on the consistency-velocity relationship rather than command outcomes, which have been explored elsewhere ([Pelletier et al., SABR 2025](https://sabr.org/analytics/presentations/2025)).

The analysis is conducted entirely in SQL, demonstrating database skills applicable to organizational biomechanics pipelines.

---

### Data Source

The OpenBiomechanics Project provides marker-based motion capture data from ~100 pitchers assessed at Driveline Baseball. Key tables:

| Table | Description |
|-------|-------------|
| `metadata` | Pitcher demographics (age, height, mass, playing level) |
| `poi` | Point-of-interest metrics per pitch (velocities, joint angles, torques, GRF) |

Data was loaded into SQLite for query execution. The full setup script is available above.

---

### Quantifying Consistency

Mechanical consistency is measured via **coefficient of variation (CV)**:

<div style="overflow-x: auto;">

$$CV = \frac{\sigma}{\mu} \times 100$$

</div>

Lower CV indicates tighter repeatability. Key metrics analyzed:

- **Torso rotational velocity** (CV_torso)
- **Shoulder internal rotation velocity** (CV_shoulder)
- **Hip-shoulder separation** (CV_hip_shoulder)
- **Arm slot** (CV_arm_slot)

---

### SQL Implementation

#### Per-Pitcher Consistency Calculation

```sql
WITH pitcher_aggregates AS (
  SELECT
    session,
    COUNT(*) as n_pitches,
    AVG(pitch_speed_mph) as mean_velo,
    AVG(max_torso_rotational_velo) as mean_torso_velo,
    STDEV(max_torso_rotational_velo) as sd_torso_velo,
    STDEV(arm_slot) as sd_arm_slot,
    AVG(arm_slot) as mean_arm_slot
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
)
SELECT
  session,
  ROUND(mean_velo, 1) as velo_mph,
  ROUND((sd_torso_velo / mean_torso_velo) * 100, 2) as cv_torso,
  ROUND((sd_arm_slot / mean_arm_slot) * 100, 2) as cv_arm_slot
FROM pitcher_aggregates
ORDER BY mean_velo DESC;
```

#### Velocity Tier Comparison

```sql
WITH pitcher_cv AS (
  SELECT
    session,
    AVG(pitch_speed_mph) as avg_velo,
    (STDEV(max_torso_rotational_velo) / AVG(max_torso_rotational_velo)) * 100 as cv_torso,
    (STDEV(arm_slot) / AVG(arm_slot)) * 100 as cv_arm_slot
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
),
tiered AS (
  SELECT *,
    CASE
      WHEN avg_velo >= 92 THEN '92+ mph'
      WHEN avg_velo >= 88 THEN '88-92 mph'
      WHEN avg_velo >= 84 THEN '84-88 mph'
      ELSE '< 84 mph'
    END as velo_tier
  FROM pitcher_cv
)
SELECT
  velo_tier,
  COUNT(*) as n_pitchers,
  ROUND(AVG(cv_torso), 3) as mean_cv_torso,
  ROUND(AVG(cv_arm_slot), 3) as mean_cv_arm_slot
FROM tiered
GROUP BY velo_tier
ORDER BY AVG(avg_velo) DESC;
```

---

### Key Findings

**Velocity Tier Analysis**

| Tier | n | Mean CV (Torso) | Mean CV (Arm Slot) |
|------|---|-----------------|-------------------|
| 92+ mph | 18 | 2.84% | 1.92% |
| 88-92 mph | 45 | 3.12% | 2.31% |
| 84-88 mph | 29 | 3.67% | 2.78% |
| < 84 mph | 8 | 4.21% | 3.45% |

Higher-velocity pitchers tend to exhibit **lower mechanical variability**, particularly in arm slot consistency. This aligns with the intuition that elite velocity requires precise, repeatable sequencing.

---

### Advanced Queries

#### Fatigue Detection via Window Functions

Tracking metric drift across throws within a session:

```sql
WITH numbered_pitches AS (
  SELECT
    session,
    pitch_speed_mph,
    arm_slot,
    ROW_NUMBER() OVER (PARTITION BY session ORDER BY session_pitch) as pitch_num,
    COUNT(*) OVER (PARTITION BY session) as total_pitches
  FROM poi
  WHERE pitch_type = 'FF'
),
early_late AS (
  SELECT
    session,
    CASE WHEN pitch_num <= 5 THEN 'early' ELSE 'late' END as phase,
    pitch_speed_mph,
    arm_slot
  FROM numbered_pitches
  WHERE total_pitches >= 10
    AND (pitch_num <= 5 OR pitch_num > total_pitches - 5)
)
SELECT
  session,
  ROUND(AVG(CASE WHEN phase = 'late' THEN pitch_speed_mph END) -
        AVG(CASE WHEN phase = 'early' THEN pitch_speed_mph END), 2) as velo_drift,
  ROUND(AVG(CASE WHEN phase = 'late' THEN arm_slot END) -
        AVG(CASE WHEN phase = 'early' THEN arm_slot END), 2) as arm_slot_drift
FROM early_late
GROUP BY session
ORDER BY velo_drift ASC;
```

#### Pitcher Profiling with NTILE

Categorizing pitchers by velocity AND consistency:

```sql
WITH pitcher_profiles AS (
  SELECT
    session,
    AVG(pitch_speed_mph) as avg_velo,
    (STDEV(max_torso_rotational_velo) / AVG(max_torso_rotational_velo) +
     STDEV(arm_slot) / AVG(arm_slot)) / 2 * 100 as avg_mechanical_cv
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
),
ranked AS (
  SELECT *,
    NTILE(4) OVER (ORDER BY avg_velo DESC) as velo_quartile,
    NTILE(4) OVER (ORDER BY avg_mechanical_cv ASC) as consistency_quartile
  FROM pitcher_profiles
)
SELECT
  session,
  ROUND(avg_velo, 1) as velo_mph,
  ROUND(avg_mechanical_cv, 2) as mech_cv_pct,
  CASE
    WHEN velo_quartile = 1 AND consistency_quartile = 1 THEN 'Elite'
    WHEN velo_quartile = 1 AND consistency_quartile = 4 THEN 'Volatile Arm'
    WHEN velo_quartile = 4 AND consistency_quartile = 1 THEN 'Consistent but Slow'
    ELSE 'Development'
  END as profile
FROM ranked
ORDER BY avg_velo DESC;
```

---

### Limitations & Extensions

**Current Limitations:**
- Single-session data (no longitudinal tracking)
- Fastballs only; breaking balls may show different consistency patterns
- No injury history to correlate with mechanical variability

**Potential Extensions:**
- Correlate consistency metrics with elbow/shoulder torque
- Compare pre/post mechanical intervention sessions
- Build predictive model for velocity gains based on consistency improvements

---

### Technical Notes

- **Database:** SQLite (portable, no server required)
- **Source Data:** [Driveline OpenBiomechanics Project](https://github.com/drivelineresearch/openbiomechanics)
- **SQL Features Used:** CTEs, window functions (NTILE, ROW_NUMBER, PARTITION BY), CASE expressions, aggregate functions, JOINs, HAVING clauses

The complete SQL file and R setup script are available for download above.
