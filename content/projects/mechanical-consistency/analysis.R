# ==========================================================
# Mechanical Consistency Analysis - College Pitchers
# Data: Driveline OpenBiomechanics Project
# ==========================================================

#### Prerequisites ####
#I think we'll only need 3 packages so this may be overkill
required_packages <- c(
  "tidyverse",    # Data manipulation
  "RSQLite", #SQLite-specific driver
  "DBI" #generic database interface
)
install_if_missing <- function(pkg) {
  if (!require(pkg, character.only = TRUE, quietly = TRUE)) {
    cat("Installing:", pkg, "\n")
    install.packages(pkg, dependencies = TRUE)
  } else {
    cat("OK:", pkg, "\n")
  }
}
for (pkg in required_packages) {
  install_if_missing(pkg)
}

library(DBI)
library(RSQLite)
library(tidyverse)

#### Setup ####

data_path <- "C:/Users/Liam/Documents/openbiomechanics/baseball_pitching/data"
db_path <- "C:/Users/Liam/Documents/mlb-analytics/content/projects/mechanical-consistency/pitching_biomechanics.db"
fig_path <- "C:/Users/Liam/Documents/mlb-analytics/content/projects"

metadata <- read_csv(file.path(data_path, "metadata.csv"))
poi <- read_csv(file.path(data_path, "poi", "poi_metrics.csv"))

#check to make sure they loaded right
cat("Metadata:",nrow(metadata),"rows\n")
cat("POI:", nrow(poi),"rows\n")

con <- dbConnect(SQLite(),db_path)
dbWriteTable(con, "metadata",metadata,overwrite=TRUE)
dbWriteTable(con,"poi",poi,overwrite=TRUE)

#verify sample query
sample_composition <- dbGetQuery(con,"
                                SELECT
                                  playing_level,
                                  COUNT(DISTINCT session) as n_pitchers,
                                  ROUND(AVG(age_yrs),1) as avg_age
                                FROM metadata
                                GROUP BY playing_level
                                ORDER BY n_pitchers DESC
                                ")
print(sample_composition)
#sample composition shows 75 college pitcher sessions, 25 other (milb/HS/ind.)
##filtered down to 41 NCAA P who threw >5 pitches in session

#### Main Analysis Query ####
pitcher_data <- dbGetQuery(con, "
                WITH college_sessions AS (
                  SELECT DISTINCT session
                  FROM metadata
                  WHERE playing_level = 'college'
                ),
                pitcher_cv AS (
                  SELECT
                    p.session,
                    COUNT(*) as n_pitches,
                    AVG(p.pitch_speed_mph) as avg_velo,
                    (STDEV(p.arm_slot) / NULLIF(AVG(p.arm_slot),0))*100 as cv_arm_slot,
                    STDEV(p.torso_lateral_tilt_br) as sd_trunk_tilt,
                    (STDEV(p.max_rotation_hip_shoulder_separation) / NULLIF(AVG(p.max_rotation_hip_shoulder_separation),0))*100 as cv_hip_shoulder,
                    (STDEV(p.stride_length) / NULLIF(AVG(p.stride_length),0))*100 as cv_stride,
                    (STDEV(p.max_pelvis_rotational_velo) / NULLIF(AVG(p.max_pelvis_rotational_velo),0))*100 as cv_pelvis_rot
                  FROM poi p
                  INNER JOIN college_sessions cs ON p.session = cs.session
                  WHERE p.pitch_type = 'FF'
                  GROUP BY p.session
                  HAVING COUNT(*) >=5
                )
                SELECT * FROM pitcher_cv
                ")

#add velocity tiers based on college dist
summary(pitcher_data$avg_velo)

pitcher_data <- pitcher_data %>%
  mutate(velo_tier = case_when(
    avg_velo >= 90 ~ "1. 90+ mph",
    avg_velo >= 86 ~ "2. 86-90 mph",
    avg_velo >= 82 ~ "3. 82-86 mph",
    TRUE ~ "4. <82 mph"
  ))
#should leave us with 6 in highest tier
pitcher_data %>% count(velo_tier)

#### Tier Summary with Confidence Intervals ####
tier_summary <- pitcher_data %>%
  group_by(velo_tier) %>%
  summarize(
    n=n(),
    mean_velo = round(mean(avg_velo),1),
    mean_cv_arm_slot = round(mean(cv_arm_slot, na.rm=TRUE),2),
    sd_cv_arm_slot = sd(cv_arm_slot, na.rm=TRUE),
    se = sd_cv_arm_slot / sqrt(n),
    ci_lower = round(mean_cv_arm_slot -1.96 * se, 2),
    ci_upper = round(mean_cv_arm_slot +1.96 * se, 2),
    mean_sd_trunk_tilt = round(mean(sd_trunk_tilt, na.rm = TRUE), 2),
    mean_cv_hip_shoulder = round(mean(cv_hip_shoulder, na.rm = TRUE), 2),
    mean_cv_stride = round(mean(cv_stride, na.rm = TRUE), 2),
    mean_cv_pelvis_rot = round(mean(cv_pelvis_rot, na.rm = TRUE), 2)
  ) %>%
  select(velo_tier, n, mean_velo, mean_cv_arm_slot, ci_lower, ci_upper,
         mean_sd_trunk_tilt, mean_cv_hip_shoulder,mean_cv_stride,mean_cv_pelvis_rot)

print(tier_summary)

#### Pitcher Profiles ####
profiles <- dbGetQuery(con,"
            WITH college_sessions AS (
            SELECT DISTINCT session
            FROM metadata
            WHERE playing_level = 'college'
            ),
            pitcher_metrics AS (
            SELECT
              p.session,
              AVG(p.pitch_speed_mph) as avg_velo,
              (STDEV(p.arm_slot) / NULLIF(AVG(p.arm_slot),0)+
              STDEV(p.stride_length) / NULLIF(AVG(p.stride_length),0) +
              STDEV(p.max_rotation_hip_shoulder_separation) / NULLIF(AVG(p.max_rotation_hip_shoulder_separation),0)+
              STDEV(p.max_pelvis_rotational_velo)/NULLIF(AVG(p.max_pelvis_rotational_velo),0)) / 4 *100 as mechanical_cv
            FROM poi p
            INNER JOIN college_sessions cs ON p.session = cs.session
            WHERE p.pitch_type = 'FF'
            GROUP BY p.session
            HAVING COUNT(*) >=5
            ),
            ranked AS (
              SELECT *,
                NTILE(4) OVER (ORDER BY avg_velo DESC) as velo_q,
                NTILE(4) OVER (ORDER BY mechanical_cv ASC) as consistency_q
              FROM pitcher_metrics
            )
            SELECT
              session,
              ROUND(avg_velo,1) as velo,
              ROUND(mechanical_cv, 2) as mech_cv,
              velo_q,
              consistency_q,
              CASE
                WHEN velo_q = 1 AND consistency_q = 1 THEN 'Elite'
                WHEN velo_q = 1 AND consistency_q = 2 THEN 'Plus Velo / Plus Consistency'
                WHEN velo_q = 1 AND consistency_q IN (3, 4) THEN 'Volatile Arm'
                WHEN velo_q = 2 AND consistency_q IN (1, 2) THEN 'Above Average'
                WHEN velo_q IN (3, 4) AND consistency_q = 1 THEN 'Consistent / Minus Velo'
                WHEN velo_q = 4 AND consistency_q = 4 THEN 'Needs Development'
                ELSE 'Average'
              END as profile
            FROM ranked
            ORDER BY avg_velo DESC
            ")
profiles %>% count(profile)

#### Statistical Validation ####

# All biomechanical correlations (expected to be minimal)
cor_arm_slot <- cor.test(pitcher_data$avg_velo, pitcher_data$cv_arm_slot, use = "complete.obs")
cor_hip_shoulder <- cor.test(pitcher_data$avg_velo, pitcher_data$cv_hip_shoulder, use = "complete.obs")
cor_stride <- cor.test(pitcher_data$avg_velo, pitcher_data$cv_stride, use = "complete.obs")
cor_pelvis <- cor.test(pitcher_data$avg_velo, pitcher_data$cv_pelvis_rot, use = "complete.obs")

# Summary
cat("\n--- Correlation Summary ---\n")
cat("Velo vs Arm Slot CV:      r =", round(cor_arm_slot$estimate, 3), ", p =", round(cor_arm_slot$p.value, 3), "\n")
cat("Velo vs Hip-Shoulder CV:  r =", round(cor_hip_shoulder$estimate, 3), ", p =", round(cor_hip_shoulder$p.value, 3), "\n")
cat("Velo vs Stride CV:        r =", round(cor_stride$estimate, 3), ", p =", round(cor_stride$p.value, 3), "\n")
cat("Velo vs Pelvis Rot CV:    r =", round(cor_pelvis$estimate, 3), ", p =", round(cor_pelvis$p.value, 3), "\n")

#### Visualizations ####
p1 <- ggplot(pitcher_data, aes(x=avg_velo, y=cv_arm_slot)) +
  geom_point(alpha = 0.7, size=2.5) +
  geom_smooth(method="lm",se=TRUE, color="steelblue",alpha=0.2) + labs(
    x="Average Fastball Velocity", y="Arm Slot CV (%)",
    title="Velo vs. Arm Slot Consistency",
    subtitle=paste0("College pitchers (n=",nrow(pitcher_data),"), r=",
                    round(cor_arm_slot$estimate,2),", p=",round(cor_arm_slot$p.value,3)),
    caption = "Data: Driveline Openbiomechanics Project") + theme_minimal() +
  theme(plot.title=element_text(face="bold"),
        plot.subtitle = element_text(color="gray40"),
        plot.background = element_rect(fill = "white", color = NA),
        panel.background = element_rect(fill = "white", color = NA)
  )

print(p1)
ggsave(file.path(fig_path, "mechanical-consistency/velo-scatter.png"),p1,width=8, height=6, dpi=300)

p2 <- ggplot(pitcher_data, aes(x=velo_tier, y=cv_arm_slot)) +
  geom_boxplot(alpha=0.6, outlier.shape = NA, fill="steelblue") +
  geom_jitter(width=0.15, alpha=0.5,size=2)+
  labs(
    x="Velocity Tier",
    y="Arm Slot CV (%)",
    title = "Mechanical Consistency by Velocity Tier",
    caption = "Data: Driveline OpenBiomechanics Project"
  ) + theme_minimal() +
  theme(
    plot.title = element_text(face="bold"),
    plot.subtitle = element_text(color="gray40"),
    plot.background = element_rect(fill = "white", color = NA),
    panel.background = element_rect(fill = "white", color = NA)
    
  )

print(p2)
ggsave(file.path(fig_path, "mechanical-consistency/tier-box.png"), p2, width=8, height=6, dpi=300)




#### Export Results ####
write_csv(pitcher_data, file.path(fig_path, "mechanical-consistency/pitcher_cv_data.csv"))
write_csv(tier_summary, file.path(fig_path, "mechanical-consistency/tier_summary.csv"))
write_csv(profiles, file.path(fig_path, "mechanical-consistency/pitcher_profiles.csv"))

dbDisconnect(con)




