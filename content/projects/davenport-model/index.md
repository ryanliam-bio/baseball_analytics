---
title: "Empirical Game Simulation: The Pythagenport Approach"
summary: "A baseline predictive model utilizing Davenport’s Pythagenport exponent to estimate game-level win probabilities from historical scoring environments."
tags:
  - Sabermetrics
  - Modeling
  - Excel
date: "2022-12-23"
weight: 100
math: true
profile: false
links:
  - icon: hero/document-chart-bar
    name: Model Architecture (Excel)
    url: "/Davenport Model.xlsx"

image:
  filename: "model.png"
  caption: "Baseline Model Output"
  focal_point: "Smart"
  preview_only: false
---

### Project Overview
This analysis represents a foundational step in my transition toward advanced game-level modeling. By implementing Clay Davenport’s **Pythagenport formula**, this model estimates expected winning percentages based on a team's runs scored and allowed within a specific seasonal environment.

### Methodology & Baseline
The objective was to evaluate the predictive accuracy of a static scoring exponent in a short-term sample.
* **Data Context**: Utilized 2021 MLB seasonal data prior to June 1st.
* **Formula Implementation**: Applied the Pythagenport exponent <br> ($Runs^{x} / (Runs^{x} + OppRuns^{x})$) to derive discrete game-by-game probabilities.
* **Application**: Developed as a benchmark for a final semester data science project evaluating full-season results against modeled win expectations.



### Critical Evaluation
While this iteration provided a functional baseline, it served primarily to identify the specific variables that require more granular modeling—many of which are now addressed in my current **Bayesian MCMC** research:

* **Inning Distributions**: This model assumes static starter length; my current work incorporates specific pitcher-level effects.
* **Sample Volatility**: The early-season noise inherent in a two-month sample highlighted the necessity for the hierarchical shrinkage methods I now employ.
* **Reliever Leverage**: Future iterations will move beyond "estimated strength" toward modeling specific reliever usage patterns and leverage.

---