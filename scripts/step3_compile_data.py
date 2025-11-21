#!/usr/bin/env python3
"""
step3_compile_data.py

Reads athlete race histories and compiles final CSVs.
Uses lifetime records for PR/All-American, and season-specific stats before nationals.
Inputs: athlete_race_history.json
Outputs: athletes.csv, races.csv
"""

import json
import logging
import pandas as pd
import numpy as np
from dateutil import parser as dateparser
from config import CONFIG

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def parse_date(dstr):
    """Parse date string to date object"""
    if dstr is None:
        return None
    try:
        return dateparser.parse(dstr).date()
    except Exception:
        return None

def is_8k_distance(section):
    """Check if distance string represents 8k"""
    if not section:
        return False
    s = section.lower()
    return any(d in s for d in ['8k', '8.0k'])

def is_track_meet(meet_name, section):
    """Check if meet is a track meet (not cross country)"""
    name = (meet_name or "").lower()
    sec = (section or "").lower()
    for kw in CONFIG["TRACK_KEYWORDS"]:
        if kw in name or kw in sec:
            if kw.strip() in ("meters", "meter", "m"):
                return True
            if kw.strip() in ("track", "indoor", "outdoor", "stadium"):
                return True
    return False

def load_athlete_data(input_file="athlete_race_history.json"):
    """Load all athlete data"""
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    athletes_by_year = {int(k): set(v) for k, v in data["athletes_by_year"].items()}
    nat_place_map = {tuple(map(int, k.split(','))): v for k, v in data["nat_place_map"].items()}
    nat_date_map = {int(k): parse_date(v) for k, v in data["nat_date_map"].items()}
    athlete_info = {int(k): v for k, v in data["athlete_info"].items()}
    athlete_histories = {int(k): v for k, v in data["athlete_histories"].items()}
    
    return athletes_by_year, nat_place_map, nat_date_map, athlete_info, athlete_histories

def extract_races_from_history(history_data):
    """Extract race list from athlete history data structure"""
    # The structure varies, but typically races are in 'results' or directly as list
    if isinstance(history_data, dict):
        if 'results' in history_data:
            return history_data['results']
        elif 'xc_results' in history_data:
            return history_data['xc_results']
        # Try to find any list in the dict
        for v in history_data.values():
            if isinstance(v, list):
                return v
    elif isinstance(history_data, list):
        return history_data
    return []

def build_athlete_snapshot_rows(athletes_by_year, nat_place_map, nat_date_map, 
                                athlete_info, athlete_histories):
    """Build athlete snapshot statistics using lifetime and season data"""
    athlete_rows = []
    
    for year in CONFIG["YEARS"]:
        nat_date = nat_date_map.get(year)
        athlete_ids = athletes_by_year.get(year, set())
        logging.info(f"Year {year}: Processing {len(athlete_ids)} athletes (nationals date: {nat_date})")
        
        for aid in athlete_ids:
            # Get athlete's race history
            history = athlete_histories.get(aid)
            if not history:
                logging.warning(f"No history found for athlete {aid}")
                continue
            
            races = extract_races_from_history(history)
            if not races:
                logging.warning(f"No races found in history for athlete {aid}")
                continue
            
            # Parse all races and filter out track meets
            all_valid_races = []
            for race in races:
                meet_name = race.get('meet_name') or race.get('name') or ""
                section = race.get('section') or ""
                race_date_str = race.get('date')
                race_date = parse_date(race_date_str)
                
                if is_track_meet(meet_name, section):
                    continue
                
                time_sec = race.get('time')
                place = race.get('place')
                
                all_valid_races.append({
                    "date": race_date,
                    "meet_name": meet_name,
                    "section": section,
                    "time": time_sec,
                    "place": place
                })
            
            # Separate lifetime 8k races and season-specific races
            lifetime_8k = [r for r in all_valid_races if is_8k_distance(r['section']) and r['time'] is not None]
            
            # Season races: only those in the target year, before nationals
            season_races = [r for r in all_valid_races if r['date'] and r['date'].year == year]
            if nat_date:
                season_races = [r for r in season_races if r['date'] < nat_date]
            
            season_8k = [r for r in season_races if is_8k_distance(r['section']) and r['time'] is not None]
            
            # Compute lifetime PR (from all 8k races ever)
            pr_time = None
            if lifetime_8k:
                times = [float(r['time']) for r in lifetime_8k]
                if times:
                    pr_time = float(np.nanmin(times))
            
            # Compute season record (best 8k in that year before nationals)
            sr_time = None
            if season_8k:
                times_s = [float(r['time']) for r in season_8k]
                if times_s:
                    sr_time = float(np.nanmin(times_s))
            
            # Compute consistency (std dev of season 8k times)
            consistency = None
            if season_8k:
                times_s = np.array([float(r['time']) for r in season_8k])
                if times_s.size >= 2:
                    consistency = float(np.std(times_s, ddof=0))
            
            # Days since season PR
            days_since_season_pr = None
            if sr_time is not None and nat_date is not None:
                # Find the date of the season PR (most recent if multiple)
                pr_races = [r for r in season_8k if r['time'] is not None and float(r['time']) == sr_time]
                if pr_races:
                    pr_dates = [r['date'] for r in pr_races if r['date'] is not None]
                    if pr_dates:
                        best_date = max(pr_dates)  # Most recent
                        days_since_season_pr = (nat_date - best_date).days
            
            # All-American status
            nat_place = nat_place_map.get((year, aid))
            all_american = 1 if (nat_place is not None and isinstance(nat_place, int) and nat_place <= 40) else 0
            
            # Get athlete info
            info = athlete_info.get(aid, {})
            athlete_name = info.get('name', '')
            athlete_class = info.get('year_in_school', '')
            school = info.get('school', '')
            
            # Number of races in season before nationals
            num_races_run = len(season_races)
            
            def nn(v):
                """Convert None/NaN to missing numeric value"""
                return CONFIG['MISSING_NUMERIC'] if (v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v)))) else v
            
            athlete_rows.append({
                "Athlete ID": aid,
                "Year": year,
                "Athlete Name": athlete_name,
                "Athlete Class": athlete_class,
                "School": school,
                "Number of Races Run": nn(num_races_run),
                "Personal Record": nn(pr_time),
                "Season Record": nn(sr_time),
                "Consistency": nn(consistency),
                "Days since Season PR": nn(days_since_season_pr),
                "All-American": all_american
            })
    
    return athlete_rows

def build_race_rows(athletes_by_year, athlete_histories):
    """Build race results for included athletes (all their races)"""
    included_athletes = set()
    for year in CONFIG["YEARS"]:
        included_athletes.update(athletes_by_year.get(year, set()))
    
    race_rows = []
    for aid in included_athletes:
        history = athlete_histories.get(aid)
        if not history:
            continue
        
        races = extract_races_from_history(history)
        if not races:
            continue
        
        for race in races:
            meet_name = race.get('meet_name') or race.get('name') or ""
            section = race.get('section') or ""
            race_date_str = race.get('date')
            race_date = parse_date(race_date_str)
            
            # Skip track meets
            if is_track_meet(meet_name, section):
                continue
            
            time_val = race.get('time')
            place_val = race.get('place')
            
            race_rows.append({
                "Athlete ID": aid,
                "Meet Date": race_date.isoformat() if race_date else None,
                "Meet Name": meet_name,
                "Race Distance": section or "",
                "Time": time_val if time_val is not None else CONFIG['MISSING_NUMERIC'],
                "Place": place_val if place_val is not None else CONFIG['MISSING_NUMERIC']
            })
    
    return race_rows

def main():
    logging.info("Loading athlete data...")
    athletes_by_year, nat_place_map, nat_date_map, athlete_info, athlete_histories = load_athlete_data()
    
    logging.info("Building athlete snapshots...")
    athlete_rows = build_athlete_snapshot_rows(athletes_by_year, nat_place_map, nat_date_map, 
                                               athlete_info, athlete_histories)
    
    logging.info("Building race results...")
    race_rows = build_race_rows(athletes_by_year, athlete_histories)
    
    # Write CSVs
    athletes_df = pd.DataFrame(athlete_rows)
    races_df = pd.DataFrame(race_rows)
    
    athletes_df.to_csv("athletes.csv", index=False)
    races_df.to_csv("races.csv", index=False)
    
    logging.info(f"Wrote athletes.csv ({len(athletes_df)} rows) and races.csv ({len(races_df)} rows).")

if __name__ == "__main__":
    main()