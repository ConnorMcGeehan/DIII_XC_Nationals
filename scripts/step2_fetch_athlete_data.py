#!/usr/bin/env python3
"""
step2_fetch_athlete_data.py

Reads nationals races, extracts athlete IDs, then fetches each athlete's 
complete race history from the API.
Inputs: nationals_races.json
Outputs: athlete_race_history.json
"""

import json
import logging
import time
import requests
from dateutil import parser as dateparser
from collections import defaultdict
from config import CONFIG

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def safe_get_json(url, params=None, max_tries=3):
    """Safely fetch JSON from API with retry logic"""
    headers = CONFIG["REQUEST_HEADERS"]
    for attempt in range(max_tries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()
            else:
                logging.warning(f"GET {url} returned {r.status_code}")
        except requests.RequestException as e:
            logging.warning(f"GET {url} failed: {e}")
        time.sleep(CONFIG["REQUEST_SLEEP"])
    logging.error(f"Failed to GET {url} after {max_tries} tries")
    return None

def parse_date(dstr):
    """Parse date string to date object"""
    if dstr is None:
        return None
    try:
        return dateparser.parse(dstr).date()
    except Exception:
        return None

def load_nationals_data(input_file="nationals_races.json"):
    """Load nationals race data from JSON"""
    with open(input_file, 'r') as f:
        nationals_list = json.load(f)
    logging.info(f"Loaded {len(nationals_list)} nationals races")
    return nationals_list

def extract_athletes_from_nationals(nationals_list):
    """Extract athlete IDs and info from nationals races"""
    athletes_by_year = defaultdict(set)
    nat_place_map = {}
    nat_date_map = {}
    athlete_info = {}  # Store basic info about each athlete
    
    for entry in nationals_list:
        year = entry['year']
        race = entry['race_data']
        
        # Track nationals date
        rd = parse_date(race.get('date'))
        if rd:
            if year not in nat_date_map:
                nat_date_map[year] = rd
            else:
                nat_date_map[year] = min(nat_date_map[year], rd)
        
        # Extract athletes
        for res in (race.get('xc_results') or []):
            runner = res.get('runner') or {}
            rid = runner.get('id')
            if rid is not None:
                athletes_by_year[year].add(rid)
                
                # Store place at nationals
                place = res.get('place')
                if place is not None:
                    existing = nat_place_map.get((year, rid))
                    if existing is None or (isinstance(place, int) and place < existing):
                        nat_place_map[(year, rid)] = place
                
                # Store athlete basic info
                if rid not in athlete_info:
                    firstname = runner.get('firstname') or ""
                    lastname = runner.get('lastname') or ""
                    athlete_info[rid] = {
                        "name": (firstname + " " + lastname).strip(),
                        "year_in_school": runner.get('year_in_school') or "",
                        "team": runner.get('team') or {},
                        "school": (runner.get('team') or {}).get('name') or ""
                    }
    
    total_athletes = sum(len(v) for v in athletes_by_year.values())
    logging.info(f"Extracted {total_athletes} unique athletes across all years")
    return dict(athletes_by_year), nat_place_map, nat_date_map, athlete_info

def fetch_athlete_race_history(athlete_id):
    """Fetch complete race history for a single athlete"""
    url = CONFIG["BASE_URL"] + CONFIG["RUNNER_ENDPOINT"] + str(athlete_id)
    data = safe_get_json(url)
    time.sleep(CONFIG["REQUEST_SLEEP"])
    return data

def save_athlete_data(athletes_by_year, nat_place_map, nat_date_map, athlete_info, 
                      athlete_histories, output_file="athlete_race_history.json"):
    """Save all athlete data including their race histories"""
    output = {
        "athletes_by_year": {str(k): list(v) for k, v in athletes_by_year.items()},
        "nat_place_map": {f"{k[0]},{k[1]}": v for k, v in nat_place_map.items()},
        "nat_date_map": {str(k): str(v) for k, v in nat_date_map.items()},
        "athlete_info": {str(k): v for k, v in athlete_info.items()},
        "athlete_histories": athlete_histories
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    logging.info(f"Saved athlete data to {output_file}")

def main():
    nationals_list = load_nationals_data()
    athletes_by_year, nat_place_map, nat_date_map, athlete_info = extract_athletes_from_nationals(nationals_list)
    
    # Collect all unique athlete IDs
    all_athlete_ids = set()
    for year_athletes in athletes_by_year.values():
        all_athlete_ids.update(year_athletes)
    
    logging.info(f"Fetching race history for {len(all_athlete_ids)} athletes...")
    
    athlete_histories = {}
    for i, athlete_id in enumerate(all_athlete_ids):
        if (i + 1) % 100 == 0:
            logging.info(f"Fetched {i + 1}/{len(all_athlete_ids)} athletes...")
        
        history = fetch_athlete_race_history(athlete_id)
        if history:
            athlete_histories[str(athlete_id)] = history
        else:
            logging.warning(f"Failed to fetch history for athlete {athlete_id}")
    
    logging.info(f"Successfully fetched {len(athlete_histories)} athlete histories")
    save_athlete_data(athletes_by_year, nat_place_map, nat_date_map, athlete_info, 
                      athlete_histories, output_file="athlete_race_history.json")

if __name__ == "__main__":
    main()