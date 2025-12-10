# EDA and Data Cleaning

# Data and Libraries
athlete_data <- read.csv("./data/athletes.csv")
race_data <- read.csv("./data/2021_23_races.csv")
library(tidyverse)


# Single-variable visualizations

# Number of Races Run
ggplot(athlete_data, aes(Number.of.Races.Run)) +
  geom_bar(fill="blue") + 
  labs(title="Number of Races Run Before National Meet", x="Number of Races", y="Number of Athletes")

# Personal Record
ggplot(athlete_data, aes(Personal.Record)) + 
  geom_histogram(fill="skyblue") +
  labs(title="Personal Record for XC 8k", x="Time (seconds)", y="Number of Athletes")

# Season Record
ggplot(athlete_data, aes(Season.Record)) + 
  geom_histogram(fill="skyblue") +
  labs(title="Season Record for XC 8k", x="Time (seconds)", y="Number of Athletes")

# Consistency
ggplot(athlete_data, aes(Consistency)) + 
  geom_histogram(fill="skyblue") +
  labs(title="Consistency of Performances", x="Standard Deviation of Times (seconds)", y="Number of Athletes")

# Days Since Season Record
ggplot(athlete_data, aes(Days.since.Season.PR)) + 
  geom_bar(fill="green") +
  labs(title="Days Since Season Record", x="Days", y="Number of Athletes")

# Time at Nationals
ggplot(race_data, aes(time)) + 
  geom_histogram(fill="skyblue") +
  labs(title="Finishing Time at Nationals", x="Time (seconds)", y="Number of Athletes")



# Multiple Variables

# Comparing Variables to All-American Status
# Number of Races Run
ggplot(athlete_data, aes(x=Number.of.Races.Run, fill=as.factor(All.American))) +
  geom_bar(position="fill") + 
  scale_fill_discrete(name = "All-American",
                      labels = c("No", "Yes")) +
  labs(title="All-American Status by Number of Races Run",
       x = "Number of Races Run",
       y = "Proportion of All-Americans")

# Personal Record and Season Record
athlete_data %>%
  filter(Personal.Record > 1350) %>%
  mutate(PR_SR = ifelse(Season.Record == Personal.Record,
                        "PR = SR",
                        "SR ≠ PR")) %>%
  ggplot(aes(x = Personal.Record, y = Season.Record, color = as.factor(All.American))) +
  geom_point() +
  scale_color_discrete(name="All-American", labels = c("0"="No", "1"="Yes")) +
  facet_wrap(~PR_SR) +
  labs(
    title = "All-American Status by Personal and Season Records",
    x = "Personal Record",
    y = "Season Record"
  )

# Consistency
ggplot(athlete_data, aes(x = Consistency, fill = as.factor(All.American))) +
  geom_density(alpha = 0.4) +
  scale_fill_manual(values = c("0" = "red", "1" = "blue"),
                    name = "All-American",
                    labels = c("No", "Yes")) +
  coord_cartesian(xlim = c(0, 150)) +
  labs(
    title = "Density of Consistency for All-Americans vs Non-All-Americans",
    x = "Consistency (Std Dev)",
    y = "Density"
  )

# Consistency compared with Season Record
ggplot(athlete_data, aes(x=Season.Record, y=Consistency)) +
  geom_density_2d_filled() +
  coord_cartesian(ylim = c(0,75), xlim = c(1400,1600)) +
  theme_minimal() +
  scale_fill_viridis_d(option = "inferno", name="Density") +
  labs(title = "Season Record Compared to Consistency",
       x = "Season Record", y="Consistency")

# Personal Record, Days Since Season PR, Consistency, and Races Run
athlete_data %>%
  filter(Personal.Record >= 1350) %>%
  filter(Consistency <= 120) %>%
  ggplot(aes(x = Days.since.Season.PR, 
             y = Consistency, 
             size = Personal.Record, 
             color = Number.of.Races.Run)) +
  geom_point(alpha = 0.6) +
  facet_wrap(~All.American, ncol = 1, labeller = labeller(All.American = c("0" = "Non All-American", "1" = "All-American"))) +
  scale_size_continuous(range = c(1, 10), name="Personal Record") +
  scale_color_viridis_c(option = "plasma", name = "Races Run") +
  labs(title = "Performance Bubble Plot",
       y = "Consistency",
       x = "Days Since Season PR") +
  theme_minimal(base_size = 12)

# Data Cleaning
cleaned_athlete_data <- athlete_data %>%
  filter(Personal.Record >= 1350 & Season.Record >= 1350) %>%
  left_join(race_data, by = c("Athlete.ID" = "athlete_id", "Year" = "year")) %>%
  select(Athlete.ID, Year, Athlete.Nam)

write.csv(cleaned_athlete_data, ".\\data\\cleaned_athlete_data.csv")