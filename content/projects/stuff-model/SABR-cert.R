library(Lahman)
library(tidyverse)
library(baseballr)
library(rpart)
library(rpart.plot)
library(ranger)
library(xgboost)


required_packages <- c(
  "tidyverse",    # Data manipulation
  "Lahman", #SQLite-specific driver
  "baseballr", #generic database interface
  "rpart",
  "rpart.plot",
  "ranger",
  "xgboost"
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



a <- c(10, 20, 40, 70, 10, 14, 18, 50)
b <- c(1, 2.2, 4.4, 6.5, 2.3, 0, 4.2, 1)
cor.test(a, b)

data_matrix <- matrix(c(5, 10, 60, 57), nrow = 2, byrow = TRUE,
                      dimnames = list(
                        "Row_Var" = c("Home Runs", "Fly Balls"),
                        "Player" = c("Pre-Injury", "Post-Injury")
                      ))
data_matrix
fisher.test(data_matrix)


##### Chapter 6 ####
x <- c(1, 5, 7, 2, 9, 10, 4, 11)
y <- c(2, 4.4, 9.9, 1, 12, 14, 5, 16)
lm(y~x)


x <- c(0.950,.540,.620,.950,.930,.70,.440,.240,.760,.95)
y <- c(0.40,.750,.870,.670,.490,.960,.440,.290,.860,.84)
lm(y ~ x)
plot(y, x)

#### Chapter 8: Tree Models ####
df <- Lahman::Teams
df$champion <- df$WSWin == "Y"
decision_tree_model <- rpart(champion ~ R + RA, data=subset(df, yearID>1999))
decision_tree_model

rpart.plot(decision_tree_model)

#decision tree for regression
df$wp <- df$W/df$G
decision_tree_regression <- rpart(wp ~R+RA, data=subset(df, yearID>1999))
decision_tree_regression
rpart.plot(decision_tree_regression)

#random forest
df$champion_factor <- factor(df$champion)
ranger(champion_factor ~ R + RA + yearID, data=subset(df, yearID>1994),num.trees=500)

x_train = as.matrix(subset(df, yearID > 1999, select=c("R","RA")))
#one for predictor variables, one for outcome
y_train = as.matrix(subset(df, yearID>1999)$champion)

model <- xgboost(data = x_train,
                 label = y_train,
                 nrounds = 100, #num boosting rounds
                 max_depth = 6, #max depth
                 eta = 0.1, #learning rate
                 objective = "binary:logistic", #regression
                 eval_metric = "logloss", #or rmse, etc.
                 nthread=2)

#homework
df <- Lahman::Teams
df$div <- df$DivWin == 'Y'
df <- df %>% select(div, W, L)
tree_hw <- rpart(div ~ W+L, data=subset(df))
rpart.plot(tree_hw)

#I would use random forest to start, then move to XGBoost once I had a better feel for the data

#### Module 10 ####
test_data <- read.csv("data_test_data_for_testing.csv")
training_data <- read.csv("training_data.csv")

RF_stuff <- ranger(run_value ~ pitch_type + release_speed + pfx_x + pfx_z + plate_x + plate_z +home_team + stand, data=training_data)
my_RF_stuff <- predict(RF_stuff, data=test_data)
test_data <- test_data %>%
  mutate(RF_STUFF = my_RF_stuff$predictions)
test_data


#Step 2: make it better
#I really wanted to include extension, so I'll need to filter out NA in both test/train
training_data_clean <- training_data%>% filter(!is.na(release_extension))

better_RF_stuff <- ranger(run_value ~ pitch_type + release_speed + pfx_x + pfx_z + plate_x + plate_z +home_team + stand +release_extension + release_spin_rate, data=training_data_clean, num.trees = 1000)

#intuitively, extension should be an improvement, but did not appear to be so without spin rate
#need to submit a prediction for every value, so instead of ignoring NA I'll use median extension
test_data_clean <- test_data %>%
  mutate(release_extension = replace_na(release_extension, 
                                        median(training_data_clean$release_extension, na.rm=TRUE)))
my_RF_stuff_2 <- predict(better_RF_stuff, data=test_data_clean)
test_data_clean <- test_data_clean %>%
  mutate(better_Stuff_1 = my_RF_stuff_2$predictions)

RF_stuff$r.squared
better_RF_stuff$r.squared

cor(test_data$RF_STUFF, test_data_clean$run_value)
cor(test_data_clean$better_Stuff_1, test_data_clean$run_value)

#R squared was consistently higher on training data, test data cor was about the same or higher


training_data_clean$stand_R <- ifelse(training_data_clean$stand == "R", 1, 0)
test_data_clean$stand_R <- ifelse(test_data_clean$stand == "R", 1, 0)

xg_params <- as.matrix(subset(training_data_clean, select=c("release_speed","pfx_x", "pfx_z","plate_x","plate_z", "stand_R")))
xg_stuff <- xgboost(data=xg_params,
                    label=training_data_clean$run_value,
                    nrounds=100,
                    max_depth=6,
                    eta=0.1,
                    objective="reg:squarederror",
                    eval_metric = "rmse",
                    nthread=2)

xg_test_params <- as.matrix(subset(test_data_clean, select=c("release_speed","pfx_x", "pfx_z","plate_x","plate_z","stand_R"))) 
my_xg_stuff <-predict(xg_stuff,newdata=xg_test_params)
test_data_clean <- test_data_clean%>%
  mutate(BETTER_STUFF = my_xg_stuff)

cor(test_data_clean$BETTER_STUFF, test_data_clean$run_value)
#increasing max depth to 8 decreased our correlation coefficient from 0.1512364 to 0.1415669
#spin rate + extension gave us cor coeff 0.1453102
#adding batter handedness increased our correlation to 0.15219


mean(abs(test_data_clean$BETTER_STUFF - test_data_clean$run_value))                                                     

mean(abs(test_data_clean$RF_STUFF - test_data_clean$run_value))


sqrt(mean((test_data_clean$BETTER_STUFF - test_data_clean$run_value)^2))
sqrt(mean((test_data_clean$RF_STUFF - test_data_clean$run_value)^2))



write.csv(test_data_clean, "submission.csv",row.names=FALSE)


#feature importance plot, suggested by Claude

#predicted vs actual run values
