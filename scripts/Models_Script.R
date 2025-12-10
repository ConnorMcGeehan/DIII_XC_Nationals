train_data <- read.csv("./data/cleaned_athlete_data.csv")
train_data %>% count(All.American)
library(tidyverse)
library(ggplot2)
library(dplyr)


## Logistic Model

model1 <- 
  glm(All.American ~ Days.since.Season.PR + Consistency + Season.Record + Personal.Record + Number.of.Races.Run, 
      data = train_data, family = binomial)
summary(model1)

## Null Model

null_model <- glm(All.American ~ 1, data = train_data, family = binomial)

summary(null_model)

# Predicted Probability
train_data$null_prob <- predict(null_model, type = "response")
train_data$null_pred <- ifelse(train_data$null_prob >= 0.5, 1, 0)

# Model 1 Predictions 
train_data <- train_data %>%
  mutate(pred_prob = predict(model1, type = "response"),
         pred_class = ifelse(pred_prob >= 0.5, 1, 0))


##Model Visualization and Evaluation

#visualize model1
train_data <- train_data %>%
  mutate(predicted_prob = predict(model1, type = "response"))
ggplot(train_data, aes(x = predicted_prob, fill = as.factor(All.American))) +
  geom_histogram(position = "identity", alpha = 0.5, bins = 30) +
  scale_fill_manual(values = c("0" = "red", "1" = "blue"),
                    name = "All-American",
                    labels = c("No", "Yes")) +
  labs(
    title = "Predicted Probabilities of Being an All-American",
    x = "Predicted Probability",
    y = "Count"
  )

#make a logistic curve for model1
ggplot(train_data, aes(x = Season.Record, y = predicted_prob, color = as.factor(All.American))) +
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

# Confusion Matrix
confusion_matrix <- table(
  Predicted = train_data$pred_class,
  Actual = train_data$All.American
)

null_confusion <- table(
  Predicted = train_data$null_pred,
  Actual = train_data$All.American
)

null_confusion
confusion_matrix

##Decision Tree Model
library(rpart)
library(rpart.plot)
tree_model <- rpart(
  as.factor(All.American) ~ Days.since.Season.PR + Consistency + Season.Record + Personal.Record + Number.of.Races.Run,
  data = train_data,
  control = rpart.control(cp = 0.01)
)
rpart.plot(tree_model, main = "Decision Tree for All-American Prediction")

