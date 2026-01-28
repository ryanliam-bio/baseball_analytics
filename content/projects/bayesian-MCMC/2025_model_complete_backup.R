### 2025 MLB Season-long Analysis ###

#### Required Packages ####
required_packages <- c(
  "tidyverse",    # Data manipulation
  "baseballr",    # Statcast data scraping
  "lubridate",    # Date handling
  "rstan",        # Bayesian modeling
  "bayesplot",    # MCMC diagnostics
  "loo",          # Model comparison
  "ggplot2",      # Visualization
  "brms",         # Bayesian Regression Models using Stan
  "pbapply",      # Progress bars
  "ggridges",     # Distribution plots
  "viridis"       # Color palettes
)
#baseballr downloaded above gives a column mismatch with Savant tables... download below
remotes::install_github("BillPetti/baseballr")

#if you want to run this code on your own and are missing packages, below should amend that
cat("Checking required packages...\n\n")

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

library(baseballr)
library(tidyverse)
library(lubridate)
library(pbapply)
library(rstan)
library(bayesplot)
library(loo)
library(ggplot2)
library(viridis)
library(brms)
library(ggridges)

#### Statcast Data Scrape ####

start_date <- as.Date("2025-03-18")
end_date <- as.Date("2025-09-28")


# Output path
output_dir <- "data"

#I want venue data to account for neutral site games
cat("Retrieving 2025 Schedule for Venue Mapping...\n")
venue_map <- tryCatch({
  mlb_schedule(season=2025)%>%
    filter(series_description == "Regular Season")%>%
    select(game_pk, venue_name) %>%
    distinct()
}, error = function(e) {
  cat("Schedule fetch failed, will default to home team venues.\n")
  return(NULL)
})

print(venue_map)

weeks <- seq(start_date, end_date, by="7 days")
date_ranges <- data.frame(
  start = weeks, end = c(weeks[-1] - 1, end_date)
)

cat("Retrieving 2025 Statcast Data...\n")
#this will take ~15 minutes
raw_list <- pblapply(1:nrow(date_ranges),function(i) {
  out <- tryCatch(
    scrape_statcast_savant(
      start_date = date_ranges$start[i],
      end_date = date_ranges$end[i],
      player_type = "pitcher"),
    error=function(e) return(NULL)
  )
  if (is.null(out) || nrow(out) == 0) return(NULL)
  
  out %>%
    filter(game_type =="R")%>%
    select(game_pk, game_date, game_type, home_team, away_team, inning, inning_topbot,
           at_bat_number, pitch_number, bat_score, post_bat_score, pitcher, player_name, events)
})


#filter out NULL values before binding
statcast_raw <- bind_rows(raw_list)

cat("Retrieved", nrow(statcast_raw), "pitches across",
    n_distinct(statcast_raw$game_pk), "games.\n")

#### Data Processing ####


#game level summary
game_info <- statcast_raw %>%
  group_by(game_pk) %>%
  summarise(
    game_date = first(game_date),
    home_team = first(home_team),
    away_team = first(away_team),
    #add a 0 to ensure max() never checks an empty list
    home_final_score = max(c(post_bat_score[inning_topbot == "Bot"], 0), na.rm = TRUE),
    away_final_score = max(c(post_bat_score[inning_topbot == "Top"], 0), na.rm = TRUE),
    .groups="drop"
  ) %>%
  left_join(venue_map, by = "game_pk") %>%
  mutate(venue = coalesce(venue_name, home_team)) %>%
  select(-venue_name)


statcast_final_pitches <- statcast_raw %>%
  arrange(game_pk, at_bat_number, pitch_number) %>% 
  group_by(game_pk, inning_topbot) %>%
  # Calculate how many runs scored since the PREVIOUS pitch for THIS team
  mutate(
    # run_delta captures every jump in score (1, 2, 3, or 4)
    run_delta = post_bat_score - lag(post_bat_score, default = 0)
  ) %>%
  # Filter for actual scoring moments
  filter(run_delta > 0) %>%
  ungroup() %>%
  mutate(
    run_outcome = run_delta,
    batting_team = ifelse(inning_topbot == "Bot", home_team, away_team),
    pitching_team = ifelse(inning_topbot == "Bot", away_team, home_team)
  )


#simply joining venue to the rest of our data
statcast_final_pitches <- statcast_final_pitches %>%
  left_join(venue_map, by = "game_pk") %>%
  mutate(venue = coalesce(venue_name, home_team))



#get starting pitchers, openers are a work in progress
# Standardized Home/Away Pitcher Mapping
#I believe this actually inverts pitcher assignment but the ID mapping later corrects that
starting_pitchers <- statcast_final_pitches %>%
  arrange(game_pk, at_bat_number) %>%
  group_by(game_pk, batting_team) %>%
  summarise(
    pitcher_name = first(player_name),
    pitcher_id = first(pitcher),
    .groups = "drop"
  ) %>%
  # Merge with game_info to determine if the batting team is home or away
  left_join(game_info %>% select(game_pk, home_team, away_team), by = "game_pk") %>%
  mutate(role = ifelse(batting_team == home_team, "home", "away")) %>%
  # Pivot using the new 'role' column
  pivot_wider(
    id_cols = game_pk,
    names_from = role,
    values_from = c(pitcher_name, pitcher_id),
    names_sep = "_" # This automatically creates pitcher_id_home, pitcher_id_away, etc.
  )



#filter to run-scoring events, max 4
run_events <- statcast_final_pitches %>%
  filter(run_outcome >0) %>%
  #due to incomplete statcast data, sometimes there are >4 run jumps that will be
  ##treated simply as 4 run jumps
  mutate(run_outcome = pmin(run_outcome, 4))

#Run outcome distribution
print(table(run_events$run_outcome))


#split by team
home_run_counts <- run_events %>%
  filter(batting_team == home_team)%>%
  group_by(game_pk) %>%
  summarise(
    home_run_1 = sum(run_outcome == 1),
    home_run_2 = sum(run_outcome == 2),
    home_run_3 = sum(run_outcome == 3),
    home_run_4 = sum(run_outcome == 4),
    .groups="drop"
  )

away_run_counts <- run_events %>%
  filter(batting_team == away_team)%>%
  group_by(game_pk) %>%
  summarise(
    away_run_1 = sum(run_outcome == 1),
    away_run_2 = sum(run_outcome == 2),
    away_run_3 = sum(run_outcome == 3),
    away_run_4 = sum(run_outcome == 4),
    .groups="drop"
  )

#combine
model_data <- game_info %>%
  left_join(starting_pitchers, by="game_pk") %>%
  left_join(home_run_counts, by="game_pk")%>%
  left_join(away_run_counts, by="game_pk")%>%
  mutate(across(starts_with("home_run_")|starts_with("away_run_"),~replace_na(.,0)))

#verify totals match, quick sanity check
model_data <- model_data %>%
  mutate(
    total_home_runs = home_run_1 + home_run_2*2 + home_run_3*3 + home_run_4*4,
    total_away_runs = away_run_1 + away_run_2*2 + away_run_3*3 + away_run_4*4,
    score_check = (total_home_runs == home_final_score) &
                  (total_away_runs == away_final_score)
  )



mismatched_games <- model_data %>%
  filter(score_check == FALSE)
cat("Diagnostic file created with", nrow(mismatched_games), "mismatches.\n")

# Only use games that are 100% verified
#our sorting left 19 games that did not match final score, likely
##due to interrupted Savant feeds. we can toss 19 and be okay.
model_data_final <- model_data %>%
  filter(score_check == TRUE)


#### Team Strength ####
rankings <- model_data_final %>%
  mutate(
    run_differential = total_home_runs - total_away_runs)

team_strengths <- rankings %>%
  select(home_team, run_differential) %>%
  rename(team=home_team) %>%
  bind_rows(
    rankings %>%
      select(away_team, run_differential) %>%
      mutate(run_differential = -run_differential) %>%
      rename(team=away_team)) %>%
  group_by(team) %>%
  summarise(
    games_played = n(),
    total_run_diff = sum(run_differential, na.rm = TRUE),
    average_run_differential = mean(run_differential, na.rm=TRUE),
    .groups = "drop"
  )

print(team_strengths)

#plot initial team run differential rankings
ggplot(team_strengths, aes(x=reorder(team, average_run_differential), y=average_run_differential,
       fill=average_run_differential))+
  geom_bar(stat="identity")+
  scale_fill_viridis_c(option="C",direction=-1)+
  coord_flip()+
  labs(x="Team", y="Average Run Differential", fill="Average Run Differential")+
  theme_minimal() + theme(legend.position = "none")



#### Park Factor Analysis ####
#calculate park factors based on runs scored at each venue
park_factors <- model_data_final %>%
  mutate(total_runs = total_home_runs + total_away_runs) %>%
  group_by(venue) %>%
  summarise(
    games = n(),
    avg_runs = mean(total_runs, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(
    league_avg = mean(avg_runs),
    park_factor = avg_runs / league_avg
  ) %>%
  arrange(desc(park_factor))

print(park_factors)

#plot park factors
ggplot(park_factors, aes(x = reorder(venue, park_factor),y = park_factor, fill = park_factor)) +
  geom_bar(stat = "identity") +
  geom_hline(yintercept = 1, linetype = "dashed", color = "red") +
  scale_fill_viridis_c(option = "D") +
  coord_flip() +
  labs(x = "Venue", y = "Park Factor",
       title = "2025 MLB Park Factors (1.0 = League Average)") +
  theme_minimal() +
  theme(legend.position = "none")
#of course, the neutral site park factors aren't very meaningful given the limited sample


#### Bayesian Model Selection: LOO-PSIS ####
model_selection <- model_data_final %>%
  select(game_pk, home_run_1, home_run_2,home_run_3,home_run_4,
         away_run_1, away_run_2, away_run_3, away_run_4) %>%
  pivot_longer(cols = -game_pk, names_to = "type",values_to="count")

#split data for each run type
scoring_vars_list <- list(
  "run_1" = model_selection%>% filter(type %in% c("home_run_1","away_run_1")),
  "run_2" = model_selection%>% filter(type %in% c("home_run_2","away_run_2")),
  "run_3" = model_selection%>% filter(type %in% c("home_run_3","away_run_3")),
  "run_4" = model_selection%>% filter(type %in% c("home_run_4","away_run_4"))
) 

#fit poisson and nbinom models
fit_poisson <- function(data) {
  brm(count ~ 1, data=data, family=poisson(),cores=4,iter=2000,chains=4)
}

fit_nbinom <- function(data) {
  brm(count ~ 1, data=data, family=negbinomial(),cores=4,iter=2000,chains=4)
}

#fit models for each run type - this will take a hot minute (8 models)
models <- list()
for (run_type in names(scoring_vars_list)) {
  cat("Fitting",run_type,"models...\n")
  models[[run_type]] <- list(
    poisson=fit_poisson(scoring_vars_list[[run_type]]),
    nbinom=fit_nbinom(scoring_vars_list[[run_type]])
  )
}

#calculate LOO for each model
loo_results <- lapply(models, function(model) {
  list(
    poisson=loo(model$poisson),
    nbinom=loo(model$nbinom)
  )
})

#compare each type
compare_results <- lapply(loo_results, function(loo_res) {
  loo_compare(loo_res$poisson, loo_res$nbinom)
})
print(compare_results)
#nbinom shows to be better model for everything except 4 run chunks
##nbinom for run type 3 was giving crazy high variance, updated to poisson

#### Modeling in Stan ####
#create indices for teams, pitchers, venues

teams <- unique(c(model_data_final$home_team, model_data_final$away_team))
pitchers <- unique(c(
  na.omit(model_data_final$pitcher_id_home),
  na.omit(model_data_final$pitcher_id_away)
))
venues <- unique(model_data_final$venue)

team_indices <- setNames(seq_along(teams),teams)
pitcher_indices <- setNames(seq_along(pitchers), as.character(pitchers))
venue_indices <- setNames(seq_along(venues), venues)

#map team names to IDs
model_data_stan <- model_data_final %>%
  mutate(
    home_team_id = team_indices[home_team],
    away_team_id = team_indices[away_team],
    venue_id = venue_indices[venue],
    home_p_idx = as.integer(pitcher_indices[as.character(pitcher_id_home)]),
    away_p_idx = as.integer(pitcher_indices[as.character(pitcher_id_away)])
  )%>%
  filter(!is.na(home_p_idx)&!is.na(away_p_idx))

stan_data <- list(
  N=nrow(model_data_stan),
  T=length(teams),
  P = length(pitchers),
  V=length(venues),
  home_team = model_data_stan$home_team_id,
  away_team = model_data_stan$away_team_id,
  home_pitcher = model_data_stan$home_p_idx,
  away_pitcher = model_data_stan$away_p_idx,
  venue = model_data_stan$venue_id,
  home_run_1 = model_data_stan$home_run_1,
  home_run_2 = model_data_stan$home_run_2,
  home_run_3 = model_data_stan$home_run_3,
  home_run_4 = model_data_stan$home_run_4,
  away_run_1 = model_data_stan$away_run_1,
  away_run_2 = model_data_stan$away_run_2,
  away_run_3 = model_data_stan$away_run_3,
  away_run_4 = model_data_stan$away_run_4
)

stan_model_code <- "
  data {
    int<lower=1> N;  // number of games
    int<lower=1> T;  // number of teams
    int<lower=1> P;  // number of pitchers
    int<lower=1> V;  // number of venues
    array[N] int home_team;
    array[N] int away_team;
    array[N] int home_pitcher;
    array[N] int away_pitcher;
    array[N] int venue;
    array[N] int home_run_1;
    array[N] int away_run_1;
    array[N] int home_run_2;
    array[N] int away_run_2;
    array[N] int home_run_3;
    array[N] int away_run_3;
    array[N] int home_run_4;
    array[N] int away_run_4;
  }
  parameters {
    // Dispersion parameters for negative binomial (runs 1-2)
    real<lower=0> theta_run_1;
    real<lower=0> theta_run_2;

    // Home advantage
    real<lower=0> home_advantage;

    // Intercepts for each run type
    real int_run_1;
    real int_run_2;
    real int_run_3;
    real int_run_4;

    // Team attack and defense (raw, to be centered)
    vector[T] att_run_1_raw;
    vector[T] def_run_1_raw;
    vector[T] att_run_2_raw;
    vector[T] def_run_2_raw;
    vector[T] att_run_3_raw;
    vector[T] def_run_3_raw;
    vector[T] att_run_4_raw;
    vector[T] def_run_4_raw;

    vector[P] pitcher_ability_raw;
    vector[V] park_effect_raw;
  }
  transformed parameters {
    // Centered team abilities
    vector[T] att_run_1 = att_run_1_raw - mean(att_run_1_raw);
    vector[T] def_run_1 = def_run_1_raw - mean(def_run_1_raw);
    vector[T] att_run_2 = att_run_2_raw - mean(att_run_2_raw);
    vector[T] def_run_2 = def_run_2_raw - mean(def_run_2_raw);
    vector[T] att_run_3 = att_run_3_raw - mean(att_run_3_raw);
    vector[T] def_run_3 = def_run_3_raw - mean(def_run_3_raw);
    vector[T] att_run_4 = att_run_4_raw - mean(att_run_4_raw);
    vector[T] def_run_4 = def_run_4_raw - mean(def_run_4_raw);

    // Centered pitcher ability
    vector[P] pitcher_ability = pitcher_ability_raw - mean(pitcher_ability_raw);

    // Centered park effects
    vector[V] park_effect = park_effect_raw - mean(park_effect_raw);
  }
  model {
    // Priors for global parameters
    home_advantage ~ normal(0, 0.1);
    int_run_1 ~ normal(0.9, 0.3);  
    int_run_2 ~ normal(-0.3, 0.3);  
    int_run_3 ~ normal(-2.0, 0.5);  
    int_run_4 ~ normal(-2.7, 0.5);   


    // Priors for dispersion parameters
    theta_run_1 ~ gamma(30, 1);
    theta_run_2 ~ gamma(30, 1);

    // Priors for team abilities
    att_run_1_raw ~ normal(0, 0.2);
    def_run_1_raw ~ normal(0, 0.2);
    att_run_2_raw ~ normal(0, 0.2);
    def_run_2_raw ~ normal(0, 0.2);
    att_run_3_raw ~ normal(0, 0.2);
    def_run_3_raw ~ normal(0, 0.2);
    att_run_4_raw ~ normal(0, 0.2);
    def_run_4_raw ~ normal(0, 0.2);

    // Priors for pitcher ability
    pitcher_ability_raw ~ normal(0, 0.2);

    // Priors for park effects
    park_effect_raw ~ normal(0, 0.1);

    // Likelihood: Negative binomial for runs 1-2, Poisson for run 3-4
    // Note: away_pitcher faces home batters, home_pitcher faces away batters
    home_run_1 ~ neg_binomial_2_log(
      att_run_1[home_team] + def_run_1[away_team] + home_advantage + int_run_1 +
      pitcher_ability[away_pitcher] + park_effect[venue],
      theta_run_1);
    away_run_1 ~ neg_binomial_2_log(
      att_run_1[away_team] + def_run_1[home_team] + int_run_1 +
      pitcher_ability[home_pitcher] + park_effect[venue],
      theta_run_1);

    home_run_2 ~ neg_binomial_2_log(
      att_run_2[home_team] + def_run_2[away_team] + home_advantage + int_run_2 +
      pitcher_ability[away_pitcher] + park_effect[venue],
      theta_run_2);
    away_run_2 ~ neg_binomial_2_log(
      att_run_2[away_team] + def_run_2[home_team] + int_run_2 +
      pitcher_ability[home_pitcher] + park_effect[venue],
      theta_run_2);

    home_run_3 ~ poisson_log(
      att_run_3[home_team] + def_run_3[away_team] + home_advantage+int_run_3+
      pitcher_ability[away_pitcher] + park_effect[venue]);
    away_run_3 ~ poisson_log(
      att_run_3[away_team] + def_run_3[home_team]+int_run_3+
      pitcher_ability[home_pitcher] + park_effect[venue]);

    home_run_4 ~ poisson_log(
      att_run_4[home_team] + def_run_4[away_team] + home_advantage + int_run_4 +
      pitcher_ability[away_pitcher] + park_effect[venue]);
    away_run_4 ~ poisson_log(
      att_run_4[away_team] + def_run_4[home_team] + int_run_4 +
      pitcher_ability[home_pitcher] + park_effect[venue]);
  }
  "

# Fit the Stan model
fit <- stan(
  model_code = stan_model_code,
  data = stan_data,
  iter = 10000,
  warmup = 2000,
  chains = 4,
  cores = 4,
  seed = 1,
  control = list(max_treedepth = 10)
)

print(fit)
traceplot(fit, pars = c("int_run_1", "int_run_2", "int_run_3", "int_run_4", "home_advantage"))
#rhat 1 and large n_eff means our sampling went well




#### Plot estimated posterior team strength ####
posterior <- rstan::extract(fit)

team_strengths_posterior <- data.frame(
  team = rep(teams, each=nrow(posterior$att_run_1)),
  att_run_1 = c(posterior$att_run_1),
  def_run_1 = c(posterior$def_run_1),
  att_run_2 = c(posterior$att_run_2),
  def_run_2 = c(posterior$def_run_2),
  att_run_3 = c(posterior$att_run_3),
  def_run_3 = c(posterior$def_run_3),
  att_run_4 = c(posterior$att_run_4),
  def_run_4 = c(posterior$def_run_4))

team_strengths_agg <- data.frame(
  team= rep(teams, each=nrow(posterior$att_run_1)),
  run_1_diff = c(posterior$att_run_1 - posterior$def_run_1),
  run_2_diff = c(posterior$att_run_2 - posterior$def_run_2),
  run_3_diff = c(posterior$att_run_3 - posterior$def_run_3),
  run_4_diff = c(posterior$att_run_4 - posterior$def_run_4))

team_strengths_long <- team_strengths_agg %>%
  pivot_longer(
    cols=c(run_1_diff, run_2_diff, run_3_diff, run_4_diff),
    names_to="metric",
    values_to="value"
  )

team_strengths_long <- team_strengths_long %>%
  mutate(team=forcats::fct_rev(factor(team)))

ggplot(team_strengths_long, aes(x=value, y=team, fill=metric))+
  geom_density_ridges(alpha=0.8) +
  theme_minimal() +
  geom_vline(xintercept=0,linetype="dashed", color=viridis::viridis(1))+
  labs(x="Strength Difference",y="Team")+
  scale_fill_viridis_d(
    name="Run Type",
    option="E",
    labels = c("1 Run","2 Runs", "3 Runs","4 Runs")
  )

#overall team strength
team_overall <- team_strengths_agg %>%
  mutate(overall_diff = run_1_diff + run_2_diff + run_3_diff + run_4_diff)%>%
  group_by(team) %>%
  summarise(
    mean_overall = mean(overall_diff),
    lower_95 = quantile(overall_diff, 0.025),
    upper_95 = quantile(overall_diff, 0.975),
    .groups="drop"
  ) %>%
  arrange(desc(mean_overall))
print(team_overall)

team_overall_posterior <- data.frame(
  team = rep(teams, each = nrow(posterior$att_run_1)),
  overall_diff = c(
    (posterior$att_run_1 - posterior$def_run_1) +
    (posterior$att_run_2 - posterior$def_run_2) +
    (posterior$att_run_3 - posterior$def_run_3) +
    (posterior$att_run_4 - posterior$def_run_4)
  )
)
# Order teams by mean overall strength
team_order <- team_overall_posterior %>%
  group_by(team) %>%
  summarise(mean_diff = mean(overall_diff)) %>%
  arrange(mean_diff) %>%
  pull(team)

team_overall_posterior <- team_overall_posterior %>%
  mutate(team = factor(team, levels = team_order))

# Ridge plot of overall team strength
ggplot(team_overall_posterior, aes(x = overall_diff, y = team, fill = after_stat(x))) +
  geom_density_ridges_gradient(scale = 2, rel_min_height = 0.01) +
  scale_fill_viridis_c(option = "C", name = "Strength") +
  geom_vline(xintercept = 0, linetype = "dashed", color = "red") +
  theme_minimal() +
  labs(x = "Overall Strength Differential", y = "Team",
       title = "2025 MLB Posterior Overall Team Strength")

#sanity check
team_strengths_agg %>%
  filter(team == "LAD") %>%
  summarise(across(where(is.numeric), mean))


#### Simulating Future Games ####

#function to map pitcher names to IDs
pitcher_lookup <- model_data_final %>%
  select(pitcher_name_home, pitcher_id_home) %>%
  rename(name=pitcher_name_home, id=pitcher_id_home) %>%
  bind_rows(
    model_data_final %>%
      select(pitcher_name_away, pitcher_id_away) %>%
      rename(name = pitcher_name_away, id=pitcher_id_away)
  ) %>%
  distinct() %>%
  filter(!is.na(name) &!is.na(id))

#quick helper function to get pitcher ID from name
get_pitcher_id <- function(name) {
  id <- pitcher_lookup$id[pitcher_lookup$name == name]
  if(length(id)==0) stop(paste("Pitcher not found:",name))
  return(id[1])
}

simulate_game <- function(home_team_name, away_team_name, home_pitcher_name, away_pitcher_name,
                          venue_name, posterior, teams, pitchers, venues, n_sims=10000,
                          neutral=FALSE, resolve_ties = TRUE) {
  home_pitcher_id <- get_pitcher_id(home_pitcher_name)
  away_pitcher_id <- get_pitcher_id(away_pitcher_name)
  
  #get indices
  h_idx <- which(teams == home_team_name)
  a_idx <- which(teams == away_team_name)
  v_idx <- which(venues == venue_name)
  hp_idx <- which(pitchers == home_pitcher_id)
  ap_idx <- which(pitchers == away_pitcher_id)
  
  n_draws <- nrow(posterior$att_run_1)
  idx <- sample(1:n_draws, n_sims, replace=TRUE)
  
  park <- posterior$park_effect[idx, v_idx]
  home_adv <- if(neutral) 0 else posterior$home_advantage[idx]
  
  #helper to compute lambda for a run type -  saves 50 lines
  get_lambda <- function(run_type, att_idx, def_idx,pitcher_idx, extra=0) {
    exp(
      posterior[[paste0("int_run_", run_type)]][idx]+
      posterior[[paste0("att_run_", run_type)]][idx,att_idx] +
      posterior[[paste0("def_run_",run_type)]][idx,def_idx]+
      posterior$pitcher_ability[idx, pitcher_idx]+
      park + extra
    )
  }
  #sim runs for each type
  simulate_runs <- function(lambda, run_type) {
    if(run_type <= 2) {  # Only use negbinom for run 1-2
      theta <- posterior[[paste0("theta_run_", run_type)]][idx]
      rnbinom(n_sims, size=theta, mu=lambda)
    } else {  # Poisson for run 3-4
      rpois(n_sims, lambda=lambda)
    }
  }
  
  home_total <- away_total <- rep(0,n_sims)
  for (r in 1:4) {
    home_lambda <- get_lambda(r, h_idx, a_idx, ap_idx, home_adv)
    away_lambda <- get_lambda(r, a_idx, h_idx, hp_idx,0)
    home_total <- home_total + r * simulate_runs(home_lambda, r)
    away_total <- away_total + r * simulate_runs(away_lambda, r)
  }
  
  if (resolve_ties) {
    extra_inning_scale <- 1/9
    ghost_runner_boost <- log(1.15/0.53) #estimated increase in run expectancy
    
    tied <- which(home_total==away_total)
    max_extras <- 20 #safety net
    extras_played <- 0
    
    while(length(tied) >0 && extras_played < max_extras) {
      n_tied <- length(tied)
      #sample new posterior indices for tied games
      extra_idx <- sample(1:n_draws, n_tied, replace=TRUE)
      
      #simulate one extra inning for tied games only
      home_extra <- away_extra <- rep(0,n_tied)
      for(r in 1:4) {
        home_lambda_extra <- extra_inning_scale * exp(
          posterior[[paste0("int_run_", r)]][extra_idx] +
            posterior[[paste0("att_run_", r)]][extra_idx, h_idx] +
            posterior[[paste0("def_run_", r)]][extra_idx, a_idx] +
            posterior$pitcher_ability[extra_idx, ap_idx] +
            posterior$park_effect[extra_idx, v_idx] +
            if(neutral) 0 else posterior$home_advantage[extra_idx] +
            ghost_runner_boost
        )
        # Away team batting
        away_lambda_extra <- extra_inning_scale * exp(
          posterior[[paste0("int_run_", r)]][extra_idx] +
            posterior[[paste0("att_run_", r)]][extra_idx, a_idx] +
            posterior[[paste0("def_run_", r)]][extra_idx, h_idx] +
            posterior$pitcher_ability[extra_idx, hp_idx] +
            posterior$park_effect[extra_idx, v_idx] +
            ghost_runner_boost
        )
        
        if (r <= 2) {
          theta <- posterior[[paste0("theta_run_", r)]][extra_idx]
          home_extra <- home_extra + r * rnbinom(n_tied, size=theta, mu=home_lambda_extra)
          away_extra <- away_extra + r * rnbinom(n_tied, size=theta, mu=away_lambda_extra)
        } else {
          home_extra <- home_extra + r * rpois(n_tied, lambda=home_lambda_extra)
          away_extra <- away_extra + r * rpois(n_tied, lambda=away_lambda_extra)
        }
      }
      
      home_total[tied] <- home_total[tied] + home_extra
      away_total[tied] <- away_total[tied] + away_extra
      
      tied <- which(home_total == away_total)
      extras_played <- extras_played + 1
      }
    }
  
  
  list(
    home_wins = mean(home_total > away_total),
    away_wins = mean(away_total > home_total),
    #this line should be unnecessary now
    ties = mean(home_total == away_total),
    home_score_mean = mean(home_total),
    away_score_mean = mean(away_total),
    home_scores = home_total,
    away_scores = away_total
  )
  
}


#reference sim w LAD v TOR, Yamamoto v Gausman
result <- simulate_game("LAD", "TOR", "Yamamoto, Yoshinobu", "Gausman, Kevin", "Dodger Stadium",
                        posterior, teams, pitchers, venues, n_sims = 10000)
#should be about 58% LAD win
print(result$home_wins)


# Create data frame from simulation results
run_data <- data.frame(
  runs = c(result$home_scores, result$away_scores),
  team = rep(c("LAD", "TOR"), each = length(result$home_scores))
)

# Histogram overlay
ggplot(run_data, aes(x = runs, fill = team, color = team)) +
  geom_histogram(binwidth = 1, position = "identity", alpha = 0.5) +
  scale_fill_manual(values = c("LAD" = "dodgerblue", "TOR" = "royalblue4")) +
  scale_color_manual(values = c("LAD" = "dodgerblue", "TOR" = "royalblue4")) +
  labs(x = "Runs Scored", y = "Frequency",
       title = "Simulated Game: LAD vs TOR") +
  theme_minimal() +
  theme(legend.title = element_blank())


calculate_metrics <- function(result, home_name = "Home", away_name = "Away") {
  home_runs <- result$home_scores
  away_runs <- result$away_scores
  
  # Probability to American odds
  
  prob_to_american <- function(p) {
    if (p >= 0.5) round(-100 * p / (1 - p)) else round(100 * (1 - p) / p)
  }
  
  # Calculate metrics
  metrics <- data.frame(
    Metric = c(
      paste(home_name, "Win %"),
      paste(away_name, "Win %"),
      paste(home_name, "Implied ML"),
      paste(away_name, "Implied ML"),
      paste(home_name, "Avg Runs"),
      paste(away_name, "Avg Runs"),
      "Projected Total",
      paste(home_name, "Spread"),
      paste(home_name, "-1.5"),
      paste(away_name, "-1.5"),
      "Over 7.5",
      "Over 8.5",
      "Over 9.5"
    ),
    Value = c(
      round(result$home_wins * 100, 1),
      round(result$away_wins * 100, 1),
      prob_to_american(result$home_wins),
      prob_to_american(result$away_wins),
      round(mean(home_runs), 2),
      round(mean(away_runs), 2),
      round(mean(home_runs + away_runs), 1),
      round(mean(home_runs - away_runs), 2),
      round(mean((home_runs - away_runs) > 1.5) * 100, 1),
      round(mean((away_runs - home_runs) > 1.5) * 100, 1),
      round(mean((home_runs + away_runs) > 7.5) * 100, 1),
      round(mean((home_runs + away_runs) > 8.5) * 100, 1),
      round(mean((home_runs + away_runs) > 9.5) * 100, 1)
    )
  )
  
  print(metrics, row.names = FALSE)
  invisible(metrics)
}


#this should give us a nice histogram showing game sim totals
plot_game_sim <- function(result, home_name, away_name,
                          home_pitcher = NULL, away_pitcher = NULL,
                          home_color = "dodgerblue", away_color = "firebrick") {
  run_data <- data.frame(
    runs = c(result$home_scores, result$away_scores),
    team = factor(rep(c(home_name, away_name), each = length(result$home_scores)),
                    levels = c(home_name, away_name))
  )
    
  # Build title and subtitle
  title <- paste0(home_name, " vs ", away_name)
  subtitle <- if (!is.null(home_pitcher) && !is.null(away_pitcher)) {
    paste0(home_pitcher, " vs ", away_pitcher)
  } else NULL
    
  # Build caption with win probabilities, condensed formatting to make it easier
  caption <- sprintf("%s %.1f%% | %s %.1f%% | O/U: %.1f",
                      home_name, result$home_wins * 100,
                      away_name, result$away_wins * 100,
                      mean(result$home_scores + result$away_scores))
    
  colors <- setNames(c(home_color, away_color), c(home_name, away_name))
    
  ggplot(run_data, aes(x = runs, fill = team, color = team)) +
    geom_histogram(binwidth = 1, position = "identity", alpha = 0.5) +
    scale_fill_manual(values = colors) +
    scale_color_manual(values = colors) +
    labs(x = "Runs Scored", y = "Frequency",
          title = title, subtitle = subtitle, caption = caption) +
    theme_minimal() +
    theme(legend.title = element_blank(),
          plot.caption = element_text(hjust = 0.5, size = 10))
}

#reference matchup number two, DET win 57.1% w total 9.2
result <- simulate_game("DET","CLE","Skubal, Tarik","Williams, Gavin",
                        "Comerica Park", posterior, teams, pitchers, venues)

calculate_metrics(result, "DET", "CLE")
plot_game_sim(result, "DET","CLE",
              home_pitcher = "Skubal, Tarik",
              away_pitcher = "Williams, Gavin",
              home_color = "midnightblue",
              away_color="red4")

