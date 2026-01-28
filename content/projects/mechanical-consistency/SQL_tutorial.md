# SQL Tutorial: Mechanical Consistency Analysis

This guide walks through SQL from scratch using the OpenBiomechanics dataset. By the end, you'll have built a complete analysis pipeline.

---

## Part 1: Setup (R + SQLite)

SQLite is a lightweight database that stores everything in a single file—no server needed. We'll use R to create it since you're already familiar with R.

### Step 1: Install Packages

Open RStudio and run:

```r
install.packages("RSQLite")
install.packages("DBI")
```

- **DBI**: Generic database interface for R
- **RSQLite**: SQLite-specific driver

### Step 2: Load Libraries and Data

```r
library(DBI)
library(RSQLite)
library(tidyverse)

# Define paths
data_path <- "C:/Users/Liam/Documents/openbiomechanics/baseball_pitching/data"
db_path <- "C:/Users/Liam/Documents/mlb-analytics/content/projects/mechanical-consistency/pitching_biomechanics.db"

# Load CSVs
metadata <- read_csv(file.path(data_path, "metadata.csv"))
poi <- read_csv(file.path(data_path, "poi", "poi_metrics.csv"))

# Check what we loaded
cat("Metadata:", nrow(metadata), "rows\n")
cat("POI:", nrow(poi), "rows\n")
```

### Step 3: Create the Database

```r
# Connect to SQLite (creates file if it doesn't exist)
con <- dbConnect(SQLite(), db_path)

# Write dataframes as tables
dbWriteTable(con, "metadata", metadata, overwrite = TRUE)
dbWriteTable(con, "poi", poi, overwrite = TRUE)

# Verify tables exist
dbListTables(con)
```

Now you have a SQLite database with two tables: `metadata` and `poi`.

---

## Part 2: SQL Fundamentals

### How to Run SQL in R

```r
# Basic pattern:
result <- dbGetQuery(con, "YOUR SQL QUERY HERE")
print(result)
```

The SQL query goes inside quotes. R sends it to the database and returns results as a dataframe.

---

### Query 1: SELECT and FROM (The Basics)

**Concept**: `SELECT` chooses columns, `FROM` specifies the table.

```r
# Get all columns, first 5 rows
dbGetQuery(con, "
  SELECT *
  FROM poi
  LIMIT 5
")
```

- `*` means "all columns"
- `LIMIT 5` restricts to 5 rows (useful for exploring)

**Try this**: Select only specific columns:

```r
dbGetQuery(con, "
  SELECT session, pitch_speed_mph, arm_slot
  FROM poi
  LIMIT 10
")
```

---

### Query 2: WHERE (Filtering Rows)

**Concept**: `WHERE` filters rows based on conditions.

```r
# Only fastballs
dbGetQuery(con, "
  SELECT session, pitch_speed_mph, arm_slot
  FROM poi
  WHERE pitch_type = 'FF'
  LIMIT 10
")
```

**Common operators**:
- `=` equals
- `>`, `<`, `>=`, `<=` comparisons
- `AND`, `OR` combine conditions
- `IN ('A', 'B')` matches multiple values

**Try this**: Fastballs over 90 mph:

```r
dbGetQuery(con, "
  SELECT session, pitch_speed_mph, max_torso_rotational_velo
  FROM poi
  WHERE pitch_type = 'FF' AND pitch_speed_mph > 90
")
```

---

### Query 3: Aggregate Functions (COUNT, AVG, MIN, MAX)

**Concept**: Aggregate functions summarize multiple rows into one value.

```r
dbGetQuery(con, "
  SELECT
    COUNT(*) as n_pitches,
    AVG(pitch_speed_mph) as avg_velo,
    MIN(pitch_speed_mph) as min_velo,
    MAX(pitch_speed_mph) as max_velo
  FROM poi
  WHERE pitch_type = 'FF'
")
```

- `COUNT(*)` counts rows
- `AVG()` calculates mean
- `as avg_velo` renames the output column (alias)

---

### Query 4: GROUP BY (Aggregating by Category)

**Concept**: `GROUP BY` splits data into groups, then aggregates each group.

```r
# Average velocity per pitcher (session)
dbGetQuery(con, "
  SELECT
    session,
    COUNT(*) as n_pitches,
    AVG(pitch_speed_mph) as avg_velo
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  LIMIT 10
")
```

**Key rule**: Every column in `SELECT` must either be in `GROUP BY` or inside an aggregate function.

---

### Query 5: HAVING (Filtering Groups)

**Concept**: `WHERE` filters rows BEFORE grouping. `HAVING` filters AFTER grouping.

```r
# Only pitchers with 5+ pitches
dbGetQuery(con, "
  SELECT
    session,
    COUNT(*) as n_pitches,
    AVG(pitch_speed_mph) as avg_velo
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
  ORDER BY avg_velo DESC
")
```

- `ORDER BY avg_velo DESC` sorts results (DESC = descending)

---

### Query 6: ROUND and Calculations

**Concept**: You can do math and format numbers in SQL.

```r
dbGetQuery(con, "
  SELECT
    session,
    COUNT(*) as n_pitches,
    ROUND(AVG(pitch_speed_mph), 1) as avg_velo,
    ROUND(AVG(max_torso_rotational_velo), 1) as avg_torso_velo
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
  ORDER BY avg_velo DESC
  LIMIT 10
")
```

---

## Part 3: Intermediate SQL

### Query 7: STDEV (Standard Deviation)

SQLite doesn't have built-in `STDEV`, but RSQLite adds it. This is key for calculating CV.

```r
dbGetQuery(con, "
  SELECT
    session,
    COUNT(*) as n_pitches,
    ROUND(AVG(pitch_speed_mph), 1) as avg_velo,
    ROUND(STDEV(pitch_speed_mph), 2) as sd_velo
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
  ORDER BY avg_velo DESC
  LIMIT 10
")
```

---

### Query 8: Calculating CV (Coefficient of Variation)

**CV = (Standard Deviation / Mean) × 100**

```r
dbGetQuery(con, "
  SELECT
    session,
    COUNT(*) as n_pitches,
    ROUND(AVG(pitch_speed_mph), 1) as avg_velo,
    ROUND((STDEV(pitch_speed_mph) / AVG(pitch_speed_mph)) * 100, 2) as cv_velo,
    ROUND((STDEV(arm_slot) / AVG(arm_slot)) * 100, 2) as cv_arm_slot
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
  ORDER BY avg_velo DESC
  LIMIT 10
")
```

This is the core of your analysis—you're calculating mechanical consistency per pitcher.

---

### Query 9: CASE Statements (Creating Categories)

**Concept**: `CASE` is like if/else in SQL.

```r
dbGetQuery(con, "
  SELECT
    session,
    AVG(pitch_speed_mph) as avg_velo,
    CASE
      WHEN AVG(pitch_speed_mph) >= 92 THEN '92+ mph'
      WHEN AVG(pitch_speed_mph) >= 88 THEN '88-92 mph'
      WHEN AVG(pitch_speed_mph) >= 84 THEN '84-88 mph'
      ELSE '< 84 mph'
    END as velo_tier
  FROM poi
  WHERE pitch_type = 'FF'
  GROUP BY session
  HAVING COUNT(*) >= 5
  LIMIT 15
")
```

---

### Query 10: CTEs (WITH Clauses)

**Concept**: CTEs (Common Table Expressions) let you break complex queries into steps. Think of them as temporary named results.

```r
dbGetQuery(con, "
  WITH pitcher_stats AS (
    SELECT
      session,
      COUNT(*) as n_pitches,
      AVG(pitch_speed_mph) as avg_velo,
      (STDEV(pitch_speed_mph) / AVG(pitch_speed_mph)) * 100 as cv_velo,
      (STDEV(arm_slot) / AVG(arm_slot)) * 100 as cv_arm_slot
    FROM poi
    WHERE pitch_type = 'FF'
    GROUP BY session
    HAVING COUNT(*) >= 5
  )
  SELECT
    session,
    ROUND(avg_velo, 1) as velo,
    ROUND(cv_velo, 2) as cv_velo,
    ROUND(cv_arm_slot, 2) as cv_arm_slot
  FROM pitcher_stats
  ORDER BY avg_velo DESC
  LIMIT 10
")
```

The `WITH pitcher_stats AS (...)` creates a temporary table called `pitcher_stats` that the main query can reference.

---

## Part 4: Advanced SQL

### Query 11: Velocity Tiers with CTEs

Combine CTEs with CASE to analyze consistency by velocity group:

```r
dbGetQuery(con, "
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
        WHEN avg_velo >= 92 THEN '1. 92+ mph'
        WHEN avg_velo >= 88 THEN '2. 88-92 mph'
        WHEN avg_velo >= 84 THEN '3. 84-88 mph'
        ELSE '4. < 84 mph'
      END as velo_tier
    FROM pitcher_cv
  )
  SELECT
    velo_tier,
    COUNT(*) as n_pitchers,
    ROUND(AVG(avg_velo), 1) as mean_velo,
    ROUND(AVG(cv_torso), 2) as mean_cv_torso,
    ROUND(AVG(cv_arm_slot), 2) as mean_cv_arm_slot
  FROM tiered
  GROUP BY velo_tier
  ORDER BY velo_tier
")
```

This is your main finding—does consistency differ by velocity tier?

---

### Query 12: JOINs (Combining Tables)

**Concept**: `JOIN` connects rows from different tables using a shared key.

```r
dbGetQuery(con, "
  SELECT
    m.playing_level,
    COUNT(DISTINCT m.session) as n_pitchers,
    ROUND(AVG(p.pitch_speed_mph), 1) as avg_velo,
    ROUND(AVG(m.age_yrs), 1) as avg_age
  FROM metadata m
  INNER JOIN poi p ON m.session_pitch = p.session_pitch
  WHERE p.pitch_type = 'FF'
  GROUP BY m.playing_level
  ORDER BY avg_velo DESC
")
```

- `m` and `p` are aliases for the table names
- `ON m.session_pitch = p.session_pitch` specifies how to match rows
- `INNER JOIN` keeps only rows that match in both tables

---

### Query 13: Window Functions (ROW_NUMBER, NTILE)

**Concept**: Window functions calculate across rows without collapsing them.

```r
# Rank pitchers by velocity within the dataset
dbGetQuery(con, "
  WITH pitcher_stats AS (
    SELECT
      session,
      AVG(pitch_speed_mph) as avg_velo
    FROM poi
    WHERE pitch_type = 'FF'
    GROUP BY session
    HAVING COUNT(*) >= 5
  )
  SELECT
    session,
    ROUND(avg_velo, 1) as velo,
    NTILE(4) OVER (ORDER BY avg_velo DESC) as velo_quartile
  FROM pitcher_stats
  ORDER BY avg_velo DESC
  LIMIT 15
")
```

- `NTILE(4)` divides rows into 4 equal groups
- `OVER (ORDER BY avg_velo DESC)` specifies the ordering for the window

---

### Query 14: Pitcher Profiles (Combining Everything)

```r
dbGetQuery(con, "
  WITH pitcher_metrics AS (
    SELECT
      session,
      AVG(pitch_speed_mph) as avg_velo,
      (STDEV(max_torso_rotational_velo) / AVG(max_torso_rotational_velo) +
       STDEV(arm_slot) / AVG(arm_slot)) / 2 * 100 as mechanical_cv
    FROM poi
    WHERE pitch_type = 'FF'
    GROUP BY session
    HAVING COUNT(*) >= 5
  ),
  ranked AS (
    SELECT *,
      NTILE(4) OVER (ORDER BY avg_velo DESC) as velo_q,
      NTILE(4) OVER (ORDER BY mechanical_cv ASC) as consistency_q
    FROM pitcher_metrics
  )
  SELECT
    session,
    ROUND(avg_velo, 1) as velo,
    ROUND(mechanical_cv, 2) as mech_cv,
    velo_q,
    consistency_q,
    CASE
      WHEN velo_q = 1 AND consistency_q = 1 THEN 'Elite'
      WHEN velo_q = 1 AND consistency_q = 4 THEN 'Volatile Arm'
      WHEN velo_q = 4 AND consistency_q = 1 THEN 'Consistent/Slow'
      ELSE 'Development'
    END as profile
  FROM ranked
  ORDER BY avg_velo DESC
")
```

---

## Part 5: Saving Your Work

### Export Query Results for Visualization

```r
# Run query and save to dataframe
tier_results <- dbGetQuery(con, "
  -- Your velocity tier query here
")

# Export to CSV for plotting
write_csv(tier_results, "tier_results.csv")

# Or plot directly in R
ggplot(tier_results, aes(x = velo_tier, y = mean_cv_torso)) +
  geom_col() +
  theme_minimal()
```

### Save Your Queries to a .sql File

Create `analysis_queries.sql` and paste your final queries there. This is what you'll offer for download on the Hugo page.

### Close the Connection

```r
dbDisconnect(con)
```

---

## SQL Syntax Cheat Sheet

| Clause | Purpose | Example |
|--------|---------|---------|
| `SELECT` | Choose columns | `SELECT session, pitch_speed_mph` |
| `FROM` | Specify table | `FROM poi` |
| `WHERE` | Filter rows | `WHERE pitch_type = 'FF'` |
| `GROUP BY` | Aggregate by category | `GROUP BY session` |
| `HAVING` | Filter after grouping | `HAVING COUNT(*) >= 5` |
| `ORDER BY` | Sort results | `ORDER BY avg_velo DESC` |
| `LIMIT` | Restrict row count | `LIMIT 10` |
| `JOIN` | Combine tables | `JOIN metadata ON ...` |
| `WITH` | Create CTE | `WITH stats AS (...)` |
| `CASE` | Conditional logic | `CASE WHEN x > 5 THEN 'high' END` |

---

## Your Assignment

Work through these queries in order:

1. ✅ Set up database (Part 1)
2. ✅ Basic exploration (Queries 1-6)
3. ✅ Calculate per-pitcher CV (Queries 7-8)
4. ✅ Create velocity tiers (Queries 9-11)
5. ✅ Add demographics with JOIN (Query 12)
6. ✅ Profile pitchers with window functions (Queries 13-14)
7. ✅ Export results and create visualizations
8. ✅ Save final queries to `analysis_queries.sql`

Good luck! Let me know when you have questions.
