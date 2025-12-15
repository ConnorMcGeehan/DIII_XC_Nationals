athlete_data <- read.csv("data/cleaned_athlete_data.csv")
library(tidyverse)
library(ggplot2)
library(dplyr)


## Logisitc Model


model1 <- glm(All.American ~ Days.since.Season.PR + Consistency + Season.Record + Personal.Record + Number.of.Races.Run, data = athlete_data, family = binomial)
summary(model1)
#run confusion matrix
library(caret)
predicted_classes <- ifelse(predict(model1, type = "response") > 0.5, 1, 0)
confusionMatrix(as.factor(predicted_classes), as.factor(athlete_data$All.American), positive = "1")
#compute and plot AUC-ROC
library(pROC)
roc_curve <- roc(athlete_data$All.American, predict(model1, type = "response"))
plot(roc_curve, main = "ROC Curve for Logistic Regression Model")
auc_value <- auc(roc_curve)
print(paste("AUC:", auc_value))

##Model Visualization

#vizualize model1
athlete_data <- athlete_data %>%
  mutate(predicted_prob = predict(model1, type = "response"))
ggplot(athlete_data, aes(x = predicted_prob, fill = as.factor(All.American))) +
  geom_histogram(position = "identity", alpha = 0.5, bins = 30) +
  scale_fill_manual(values = c("0" = "red", "1" = "blue"),
                    name = "All-American",
                    labels = c("No", "Yes")) +
  labs(
    title = "Predicted Probabilities of Being an All-American",
    x = "Predicted Probability",
    y = "Count"
  )

#make a logisitc curve for model1
ggplot(athlete_data, aes(x = Season.Record, y = predicted_prob, color = as.factor(All.American))) +
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


##Decision Tree Model

library(rpart)
library(rpart.plot)
tree_model <- rpart(
  as.factor(All.American) ~ Days.since.Season.PR + Consistency + Season.Record + Personal.Record + Number.of.Races.Run,
  data = athlete_data,
  control = rpart.control(cp = 0.01)
)
rpart.plot(tree_model, main = "Decision Tree for All-American Prediction")
#confusion matrix for decision tree
tree_predicted_classes <- predict(tree_model, type = "class")
confusionMatrix(tree_predicted_classes, as.factor(athlete_data$All.American), positive = "1")
#compute and plot AUC-ROC for decision tree
tree_probs <- predict(tree_model, type = "prob")[,2]
roc_curve_tree <- roc(athlete_data$All.American, tree_probs)
plot(roc_curve_tree, main = "ROC Curve for Decision Tree Model")
auc_value_tree <- auc(roc_curve_tree)
print(paste("AUC (Decision Tree):", auc_value_tree))


##Random Forest Model
library(randomForest)
set.seed(123)
rf_model <- randomForest(
  as.factor(All.American) ~ Days.since.Season.PR + Consistency + Season.Record + Personal.Record + Number.of.Races.Run,
  data = athlete_data,
  ntree = 500,
  mtry = 3,
  importance = TRUE
)
print(rf_model)
varImpPlot(rf_model, main = "Variable Importance in Random Forest Model")
#confusion matrix for random forest
rf_predicted_classes <- predict(rf_model)
confusionMatrix(rf_predicted_classes, as.factor(athlete_data$All.American), positive = "1")
#compute and plot AUC-ROC for random forest
rf_probs <- predict(rf_model, type = "prob")[,2]
roc_curve_rf <- roc(athlete_data$All.American, rf_probs)
plot(roc_curve_rf, main = "ROC Curve for Random Forest Model")
auc_value_rf <- auc(roc_curve_rf)
print(paste("AUC (Random Forest):", auc_value_rf))


  