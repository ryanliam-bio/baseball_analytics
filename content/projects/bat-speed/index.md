---
title: "Bat Speed Analysis 1.0"
summary: "A cursory look at swing velocity data using Python, specifically year over year changes."
date: 2025-06-30
tags:
  - Python
  - Biomechanics
  - Statcast
  - Featured
math: true
share: false
profile: false
weight: 20
image:
  caption: 'YoY Bat Speed/Length $\Delta$'
  focal_point: "Smart"
  preview_only: false
---

<a href="bat-speed-trials.ipynb" download="MLB_Bat_Speed_Analysis.ipynb" class="btn btn-primary">
  📥 Download Full Notebook
</a>

### Project Overview
This project serves as a kinematic exploration of the Statcast bat-tracking dataset. The focus is twofold: quantifying year-over-year (YoY) stability in swing velocity and deriving secondary metrics like **radial acceleration** to better understand the physical profiles of elite hitters.

### Methodology
While the primary data was sourced from Statcast leaderboards, this analysis dives into individual swing sets to map player-specific quantiles (5th through 95th percentiles). This granular approach allows for a better understanding of a hitter's "velocity ceiling" versus their "mechanical floor".

#### **Derived Metric: Proxy Acceleration**
To move beyond raw velocity, I calculated a kinematic acceleration profile using average bat speed (converted to ft/s) and swing length:
$$a = \frac{v^2}{L}$$
*Note: While this assumes constant acceleration, it provides a solid baseline for identifying hitters who generate speed through high-efficiency mechanics versus those who rely on longer swing paths. This serves as an indirect proxy for full-scope biomechanical tracking.*



A critical finding during the sanity check of the individual swing exports revealed a 25,000-row limit on standard Savant exports. Because the export appears to prioritize higher velocity readings, hitters with lower average bat speeds—such as **Jacob Wilson**—had their data truncated or entirely excluded from the sample. 

This discovery highlights the necessity of using segmented or "chunked" data requests to ensure the full spectrum of swing profiles is represented, particularly when analyzing hitters who rely on contact over raw power.

**Future Iterations (Feb 2026):**
* Implementation of a chunked scraping process to bypass export limits.
* Adjustment of acceleration metrics for depth of contact and swing plane.
* Expanded YoY analysis as 2026 spring training data becomes available.