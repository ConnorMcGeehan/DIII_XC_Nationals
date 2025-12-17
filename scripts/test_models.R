# Test Models on 2025 Data
# This script loads the trained models and evaluates them on 2025 test data

library(tidyverse)
library(caret)
library(pROC)


test_data <- read.csv("./data/2025_results.csv")

# Check the data
print("Test Data Summary:")
print(paste("Total observations:", nrow(test_data)))
print(paste("Years in data:", unique(test_data$Year)))
print(paste("Total All-Americans:", sum(test_data$All.American)))

# Clean column names
colnames(test_data) <- gsub(" ", ".", colnames(test_data))

model_logistic <- readRDS("models/logistic_model.rds")
model_tree <- readRDS("models/tree_model.rds")
model_rf <- readRDS("models/rf_model.rds")


# Logistic Regression predictions
test_data <- test_data %>%
  mutate(pred_prob_logistic = predict(model_logistic, newdata = ., type = "prob")$Yes)

# Decision Tree predictions
test_data <- test_data %>%
  mutate(pred_prob_tree = predict(model_tree, newdata = ., type = "prob")$Yes)

# Random Forest predictions
test_data <- test_data %>%
  mutate(pred_prob_rf = predict(model_rf, newdata = ., type = "prob")$Yes)




# Logistic Regression
roc_logistic <- roc(test_data$All.American, test_data$pred_prob_logistic)
auc_logistic <- auc(roc_logistic)

# Decision Tree
roc_tree <- roc(test_data$All.American, test_data$pred_prob_tree)
auc_tree <- auc(roc_tree)

# Random Forest
roc_rf <- roc(test_data$All.American, test_data$pred_prob_rf)
auc_rf <- auc(roc_rf)

# Plot all ROC curves together
plot(roc_logistic, col = "blue", main = "ROC Curves - Test Data (2025)")
plot(roc_tree, col = "red", add = TRUE)
plot(roc_rf, col = "green", add = TRUE)
legend("bottomright", 
       legend = c(paste("Logistic Regression (AUC =", round(auc_logistic, 3), ")"),
                  paste("Decision Tree (AUC =", round(auc_tree, 3), ")"),
                  paste("Random Forest (AUC =", round(auc_rf, 3), ")")),
       col = c("blue", "red", "green"),
       lwd = 2)


# Top-40 Evaluation on Test Data

# Function to calculate top-40 accuracy
calculate_top40_accuracy <- function(data, prob_col, year_col = "Year") {
  data %>%
    group_by(.data[[year_col]]) %>%
    arrange(.data[[year_col]], desc({{ prob_col }})) %>%
    slice_head(n = 40) %>%
    summarise(
      actual_all_americans = sum(All.American),
      accuracy = mean(All.American),
      .groups = 'drop'
    )
}

# Calculate for each model
top40_logistic <- calculate_top40_accuracy(test_data, pred_prob_logistic)
top40_tree <- calculate_top40_accuracy(test_data, pred_prob_tree)
top40_rf <- calculate_top40_accuracy(test_data, pred_prob_rf)

print(top40_logistic)
print(paste("Overall:", sum(top40_logistic$actual_all_americans), "out of 40",
            "(", round(mean(top40_logistic$accuracy) * 100, 1), "% accuracy)"))

print(top40_tree)
print(paste("Overall:", sum(top40_tree$actual_all_americans), "out of 40",
            "(", round(mean(top40_tree$accuracy) * 100, 1), "% accuracy)"))

print(top40_rf)
print(paste("Overall:", sum(top40_rf$actual_all_americans), "out of 40",
            "(", round(mean(top40_rf$accuracy) * 100, 1), "% accuracy)"))

# Create comparison summary
test_comparison <- data.frame(
  Model = c("Logistic Regression", "Decision Tree", "Random Forest"),
  AUC = c(round(auc_logistic, 4), round(auc_tree, 4), round(auc_rf, 4)),
  Top40_Correct = c(sum(top40_logistic$actual_all_americans),
                    sum(top40_tree$actual_all_americans),
                    sum(top40_rf$actual_all_americans)),
  Top40_Accuracy = c(round(mean(top40_logistic$accuracy) * 100, 1),
                     round(mean(top40_tree$accuracy) * 100, 1),
                     round(mean(top40_rf$accuracy) * 100, 1))
)

print(test_comparison)

# Confusion Matrices

# Find optimal cutoffs for test data
coords_logistic <- coords(roc_logistic, "best", ret = "threshold",
                          best.method = "closest.topleft")
coords_tree <- coords(roc_tree, "best", ret = "threshold",
                      best.method = "closest.topleft")
coords_rf <- coords(roc_rf, "best", ret = "threshold",
                    best.method = "closest.topleft")

# Create predicted classes
test_data <- test_data %>%
  mutate(
    pred_class_logistic = ifelse(pred_prob_logistic >= coords_logistic$threshold, 1, 0),
    pred_class_tree = ifelse(pred_prob_tree >= coords_tree$threshold, 1, 0),
    pred_class_rf = ifelse(pred_prob_rf >= coords_rf$threshold, 1, 0)
  )

# Logistic Regression Confusion Matrix
print(paste("Optimal Cutoff:", round(coords_logistic$threshold, 3)))
confusionMatrix(as.factor(test_data$pred_class_logistic),
                as.factor(test_data$All.American),
                positive = "1")

# Decision Tree Confusion Matrix
print(paste("Optimal Cutoff:", round(coords_tree$threshold, 3)))
confusionMatrix(as.factor(test_data$pred_class_tree),
                as.factor(test_data$All.American),
                positive = "1")

# Random Forest Confusion Matrix
print(paste("Optimal Cutoff:", round(coords_rf$threshold, 3)))
confusionMatrix(as.factor(test_data$pred_class_rf),
                as.factor(test_data$All.American),
                positive = "1")



# For the chosen model (Logistic Regression), show detailed results
test_data_ranked <- test_data %>%
  arrange(desc(pred_prob_logistic)) %>%
  mutate(predicted_rank = row_number(),
         predicted_top40 = ifelse(predicted_rank <= 40, 1, 0))

# Athletes we predicted as All-Americans who weren't
false_positives <- test_data_ranked %>%
  filter(predicted_top40 == 1 & All.American == 0) %>%
  select(Athlete.Name, School, Season.Record, pred_prob_logistic, Nationals.Place)

print(false_positives)

# All-Americans we missed in our top 40
false_negatives <- test_data_ranked %>%
  filter(predicted_top40 == 0 & All.American == 1) %>%
  select(Athlete.Name, School, Season.Record, pred_prob_logistic, Nationals.Place, predicted_rank)

print(false_negatives)


# Histogram of predicted probabilities (Logistic Regression)
ggplot(test_data, aes(x = pred_prob_logistic, fill = as.factor(All.American))) +
  geom_histogram(position = "stack", bins = 30) +
  scale_fill_manual(values = c("0" = "red", "1" = "blue"),
                    name = "All-American",
                    labels = c("No", "Yes")) +
  labs(
    title = "Predicted Probabilities - Test Data 2025 (Logistic Regression)",
    x = "Predicted Probability",
    y = "Count"
  )

# Scatter plot: Predicted probability vs Nationals Place
ggplot(test_data, aes(x = Nationals.Place, y = pred_prob_logistic, 
                      color = as.factor(All.American))) +
  geom_point(size = 2, alpha = 0.7) +
  geom_hline(yintercept = coords_logistic$threshold, linetype = "dashed", color = "black") +
  scale_color_manual(values = c("0" = "red", "1" = "blue"),
                     name = "All-American",
                     labels = c("No", "Yes")) +
  labs(
    title = "Predicted Probability vs Actual Nationals Place",
    subtitle = "Dashed line shows optimal cutoff",
    x = "Nationals Place (lower is better)",
    y = "Predicted Probability"
  )

# Comparison bar plot
top40_comparison_long <- data.frame(
  Model = rep(c("Logistic", "Tree", "Random Forest"), each = 1),
  Accuracy = c(mean(top40_logistic$accuracy), 
               mean(top40_tree$accuracy), 
               mean(top40_rf$accuracy))
)

ggplot(top40_comparison_long, aes(x = Model, y = Accuracy, fill = Model)) +
  geom_bar(stat = "identity") +
  geom_text(aes(label = paste0(round(Accuracy * 100, 1), "%")), 
            vjust = -0.5, size = 5) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1)) +
  scale_fill_manual(values = c("Logistic" = "blue", "Tree" = "red", "Random Forest" = "green")) +
  labs(
    title = "Top-40 Accuracy on 2025 Test Data",
    x = "Model",
    y = "Accuracy (% of top 40 that were All-Americans)"
  ) +
  theme_minimal()

