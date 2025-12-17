# Cross Country All-American Prediction Project

## Project Overview
This project aims to predict **NCAA Division III Cross Country All-Americans** using machine learning models trained on historical nationals data from **2021–2023** and tested on **2025** results. The goal is to identify which athletes will earn All-American honors (top 40 finishers at nationals) based on their season performance metrics.

---

## Problem Statement
Each year, exactly **40 athletes** earn All-American honors at the NCAA Division III Cross Country Championships. While season performance provides some indication of who might succeed at nationals, race-day conditions, tactical racing, and peak timing introduce uncertainty.

This project explores whether machine learning models can improve upon naive prediction methods by incorporating multiple performance indicators beyond just season-best times.

---

## Dataset

### Training Data
- **Source:** NCAA DIII Cross Country Nationals results (2021–2023)  
- **Size:** 3 years of data, 120 total All-Americans  
- **File:** `./data/cleaned_athlete_data.csv`

### Test Data
- **Source:** NCAA DIII Cross Country Nationals results (2025)  
- **Size:** 291 athletes, 40 All-Americans  
- **File:** `./data/2025_results.csv`

---

## Features

- **Season Record:** Athlete's fastest 8K time during the season  
- **Personal Record:** Athlete's all-time fastest 8K time  
- **Consistency:** Standard deviation of race times throughout the season  
- **Days Since Season PR:** Days between season-best performance and nationals  
- **Number of Races Run:** Total races competed in during the season  
- **Year:** Competition year  
- **All-American:** Binary target variable (`1 = All-American`, `0 = Not`)

---

## Data Processing
- **Multicollinearity Check:**  
  - *Personal Record* was removed due to high correlation (> 0.8) with *Season Record*
- **Final Features Used:**  
  - Season Record  
  - Consistency  
  - Days Since Season PR  
  - Number of Races Run  

---

## Methodology

### Models Evaluated
- **Logistic Regression** *(chosen model)*  
- Decision Tree  
- Random Forest  

### Cross-Validation
- **Method:** 10-fold cross-validation  
- **Purpose:** Honest out-of-sample performance estimation without touching test data  
- **Implementation:** All evaluation metrics use cross-validated predictions to reduce overfitting  

---

## Evaluation Metrics

### Primary Metric
- **Top-40 Accuracy:**  
  Percentage of the top 40 predicted athletes who were actually All-Americans  

This metric directly reflects the real-world constraint that **exactly 40 athletes** are selected.

### Secondary Metrics
- **AUC-ROC:** Area under the receiver operating characteristic curve  
- **Confusion Matrix:** Using optimal cutoff from ROC curve (closest-to-top-left method)  
- **Sensitivity, Specificity, Precision**

---

## Baseline Comparison
- **Naive Baseline:** Selecting the top 40 athletes by fastest season record  
- **Baseline Performance:**  
  - 26 / 40 correct  
  - **65.0% accuracy**

---
