import json
import pandas as pd

# --- Load the athlete history JSON ---
with open("athlete_race_history.json", "r") as f:
    data = json.load(f)

athletes = data["athlete_histories"]

records = []

# Helper: identify nationals meet names
NATIONALS_KEYWORDS = [
    "NCAA Division III Cross Country Championships",
    "NCAA Division 3 Cross Country Championships",
    "NCAA DIII Cross Country Championships"
]

def is_nationals(meet_name):
    if meet_name is None:
        return False
    return any(key in meet_name for key in NATIONALS_KEYWORDS)


# --- Extract nationals results for 2021–2023 ---
for athlete_id, athlete in athletes.items():
    seasons = athlete.get("season_ratings", [])

    for season in seasons:
        year = season["season"]["year"]

        if year not in [2021, 2022, 2023]:
            continue

        # XC races for the season
        xc_races = season.get("season_xc_performances", [])

        for race in xc_races:
            race_info = race.get("race", {})
            meet_name = race_info.get("meet_name")
            time = race.get("time")
            place = race.get("place")

            # Only include NATIONALS results
            if not is_nationals(meet_name):
                continue

            records.append({
                "athlete_id": athlete_id,
                "year": year,
                "meet_name": meet_name,
                "time": time,
                "place": place  # will be fixed later if None
            })

# Convert to dataframe
df = pd.DataFrame(records)

# --- Fix missing places in 2021 and 2022 by ranking times ---
for yr in [2021, 2022]:
    sub = df[df["year"] == yr].copy()

    if len(sub) == 0:
        continue

    # Rank by time (ascending)
    sub = sub.sort_values("time")
    sub["place"] = range(1, len(sub) + 1)

    # Update original df
    df.loc[sub.index, "place"] = sub["place"]

# --- Add All-American flag (top 40) ---
df["all_american"] = (df["place"] <= 40).astype(int)

# --- Save to CSV ---
df.to_csv("../data/2021_23_races.csv", index=False)

df.head()
