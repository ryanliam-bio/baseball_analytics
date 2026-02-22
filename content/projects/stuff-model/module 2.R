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


#### Module 9 ####


