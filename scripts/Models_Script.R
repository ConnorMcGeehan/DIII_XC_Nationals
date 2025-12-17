train_data <- read.csv("./data/cleaned_athlete_data.csv")

library(tidyverse)
library(ggplot2)
library(dplyr)
library(caret)
library(pROC)

# Correlation matrix for numeric predictors
cor_matrix <- train_data %>%
  select(Days.since.Season.PR, Consistency, Season.Record, 
         Personal.Record, Number.of.Races.Run) %>%
  cor()
print("Correlation Matrix:")
print(round(cor_matrix, 3))

train_data <- train_data %>% select(-Personal.Record)

# Set up 10-fold cross-validation
set.seed(123)
train_control <- trainControl(
  method = "cv",
  number = 10,
  savePredictions = "final",
  classProbs = TRUE,
  summaryFunction = twoClassSummary
)

# Need to convert outcome to factor with valid names for caret
train_data_cv <- train_data %>%
  mutate(all_american_factor = factor(all_american, 
                                      levels = c(0, 1), 
                                      labels = c("No", "Yes")))

# Train model with CV
model1_cv <- train(
  all_american_factor ~ Days.since.Season.PR + Consistency + Season.Record + 
    Number.of.Races.Run,
  data = train_data_cv,
  method = "glm",
  family = "binomial",
  trControl = train_control,
  metric = "ROC"
)

# Logistic regression CV results
print(model1_cv)
print(model1_cv$results)

# Get CV predictions (out-of-sample) from logistic regression
train_data <- train_data %>%
  mutate(pred_prob_logistic = model1_cv$pred %>%
           arrange(rowIndex) %>%
           pull(Yes))

# Decision Tree

library(rpart)
library(rpart.plot)

set.seed(123)
tree_model_cv <- train(
  all_american_factor ~ Days.since.Season.PR + Consistency + Season.Record + 
    Number.of.Races.Run,
  data = train_data_cv,
  method = "rpart",
  trControl = train_control,
  metric = "ROC",
  tuneLength = 10
)

# Decision tree CV results
print(tree_model_cv)
print(tree_model_cv$results)

# Plot best tree
rpart.plot(tree_model_cv$finalModel, main = "Decision Tree for All-American Prediction")

# Get CV predictions (out-of-sample) from decision tree
tree_cv_preds <- model1_cv$pred %>%
  arrange(rowIndex) %>%
  pull(Yes)

# Match CV predictions back to original data
# The predictions are in the same order as train_data_cv
train_data <- train_data %>%
  mutate(pred_prob_tree = tree_model_cv$pred %>%
           arrange(rowIndex) %>%
           pull(Yes))

# Random Forest

library(randomForest)

set.seed(123)
rf_model_cv <- train(
  all_american_factor ~ Days.since.Season.PR + Consistency + Season.Record + 
    Number.of.Races.Run,
  data = train_data_cv,
  method = "rf",
  trControl = train_control,
  metric = "ROC",
  tuneGrid = expand.grid(mtry = c(2, 3, 4)),
  ntree = 500
)

# Random Forest CV results
print(rf_model_cv)
print(rf_model_cv$results)

# Variable importance
varImp(rf_model_cv)
plot(varImp(rf_model_cv), main = "Variable Importance in Random Forest Model")

# Get CV predictions (out-of-sample) from random forest
train_data <- train_data %>%
  mutate(pred_prob_rf = rf_model_cv$pred %>%
           arrange(rowIndex) %>%
           pull(Yes))

# ROC Curves and AUC Comparison

# Logistic Regression
roc_logistic <- roc(train_data$all_american, train_data$pred_prob_logistic)
auc_logistic <- auc(roc_logistic)

# Decision Tree
roc_tree <- roc(train_data$all_american, train_data$pred_prob_tree)
auc_tree <- auc(roc_tree)

# Random Forest
roc_rf <- roc(train_data$all_american, train_data$pred_prob_rf)
auc_rf <- auc(roc_rf)

# Plot all ROC curves together
plot(roc_logistic, col = "blue", main = "ROC Curves for All Models")
plot(roc_tree, col = "red", add = TRUE)
plot(roc_rf, col = "green", add = TRUE)
legend("bottomright", 
       legend = c(paste("Logistic Regression (AUC =", round(auc_logistic, 3), ")"),
                  paste("Decision Tree (AUC =", round(auc_tree, 3), ")"),
                  paste("Random Forest (AUC =", round(auc_rf, 3), ")")),
       col = c("blue", "red", "green"),
       lwd = 2)

# Top 40 Per Year Evaluation

# Function to calculate top-40 accuracy per year
calculate_top40_accuracy <- function(data, prob_col) {
  data %>%
    group_by(Year) %>%
    arrange(Year, desc({{ prob_col }})) %>%
    slice_head(n = 40) %>%
    summarise(
      actual_all_americans = sum(all_american),
      accuracy = mean(all_american)
    ) %>%
    ungroup()
}

# Calculate for each model
top40_logistic <- calculate_top40_accuracy(train_data, pred_prob_logistic)
top40_tree <- calculate_top40_accuracy(train_data, pred_prob_tree)
top40_rf <- calculate_top40_accuracy(train_data, pred_prob_rf)

# Create comparison summary
model_comparison <- data.frame(
  Model = c("Logistic Regression", "Decision Tree", "Random Forest"),
  AUC = c(round(auc_logistic, 4), round(auc_tree, 4), round(auc_rf, 4)),
  Top40_Correct = c(sum(top40_logistic$actual_all_americans),
                    sum(top40_tree$actual_all_americans),
                    sum(top40_rf$actual_all_americans)),
  Top40_Accuracy = c(round(mean(top40_logistic$accuracy) * 100, 1),
                     round(mean(top40_tree$accuracy) * 100, 1),
                     round(mean(top40_rf$accuracy) * 100, 1))
)

# Model Comparison Summary
print(model_comparison)


# Confusion Matrices

# Use optimal cutoff from ROC curve for each model
coords_logistic <- coords(roc_logistic, "best", ret = "threshold",
                          best.method = "closest.topleft")
coords_tree <- coords(roc_tree, "best", ret = "threshold",
                      best.method = "closest.topleft")
coords_rf <- coords(roc_rf, "best", ret = "threshold",
                    best.method = "closest.topleft")

# Create predicted classes using optimal cutoffs
train_data <- train_data %>%
  mutate(
    pred_class_logistic = ifelse(pred_prob_logistic >= coords_logistic$threshold, 1, 0),
    pred_class_tree = ifelse(pred_prob_tree >= coords_tree$threshold, 1, 0),
    pred_class_rf = ifelse(pred_prob_rf >= coords_rf$threshold, 1, 0)
  )

# Logistic Regression Confusion Matrix
print(paste("Optimal Cutoff:", round(coords_logistic$threshold, 3)))
confusionMatrix(as.factor(train_data$pred_class_logistic),
                as.factor(train_data$all_american),
                positive = "1")

# Decision Tree Confusion Matrix
print(paste("Optimal Cutoff:", round(coords_tree$threshold, 3)))
confusionMatrix(as.factor(train_data$pred_class_tree),
                as.factor(train_data$all_american),
                positive = "1")

# Random Forest Confusion Matrix
print(paste("Optimal Cutoff:", round(coords_rf$threshold, 3)))
confusionMatrix(as.factor(train_data$pred_class_rf),
                as.factor(train_data$all_american),
                positive = "1")


# Visualizations

# Histogram of predicted probabilities
ggplot(train_data, aes(x = pred_prob_logistic, fill = as.factor(all_american))) +
  geom_histogram(position = "stack", bins = 30) +
  scale_fill_manual(values = c("0" = "red", "1" = "blue"),
                    name = "All-American",
                    labels = c("No", "Yes")) +
  labs(
    title = "Predicted Probabilities of Being an All-American (Logistic Regression)",
    x = "Predicted Probability",
    y = "Count"
  )

# Logistic curve
ggplot(train_data, aes(x = Season.Record, y = pred_prob_logistic, 
                       color = as.factor(all_american))) +
  geom_point() +
  geom_smooth(method = "glm", method.args = list(family = "binomial"), se = FALSE) +
  scale_color_manual(values = c("0" = "red", "1" = "blue"),
                     name = "All-American",
                     labels = c("No", "Yes")) +
  labs(
    title = "Logistic Curve of Predicted Probabilities by Season Record",
    x = "Season Record",
    y = "Predicted Probability"
  )

# Comparison bar plot for top-40 accuracy
top40_comparison_long <- data.frame(
  Model = rep(c("Logistic", "Tree", "Random Forest"), each = 3),
  Year = rep(top40_logistic$Year, 3),
  Accuracy = c(top40_logistic$accuracy, top40_tree$accuracy, top40_rf$accuracy)
)

ggplot(top40_comparison_long, aes(x = as.factor(Year), y = Accuracy, fill = Model)) +
  geom_bar(stat = "identity", position = "dodge") +
  scale_y_continuous(labels = scales::percent) +
  scale_fill_manual(values = c("Logistic" = "blue", "Tree" = "red", "Random Forest" = "green")) +
  labs(
    title = "Top-40 Accuracy by Year and Model",
    x = "Year",
    y = "Accuracy (% of top 40 that were All-Americans)"
  )


# Save models

saveRDS(model1_cv, "./models/logistic_model.rds")
saveRDS(tree_model_cv, "./models/tree_model.rds")
saveRDS(rf_model_cv, "./models/rf_model.rds")


