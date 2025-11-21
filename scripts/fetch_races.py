#!/usr/bin/env python3
"""
step3_compile_data.py

Reads nationals races and athlete metadata, compiles final CSVs.
Inputs: nationals_races.json, athlete_metadata.json
Outputs: athletes.csv, races.csv
"""

import json
import logging
import pandas as pd
import numpy as np
from dateutil import parser as dateparser
from collections import defaultdict
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

def is_8k_distance(dist_str):
    """Check if distance string represents 8k"""
    if not dist_str:
        return False
    return dist_str.lower().startswith('8')

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

def load_all_metadata():
    """Load previously saved metadata"""
    with open("athlete_metadata.json", 'r') as f:
        metadata = json.load(f)
    
    athletes_by_year = {int(k): set(v) for k, v in metadata["athletes_by_year"].items()}
    nat_place_map = {tuple(map(int, k.split(','))): v for k, v in metadata["nat_place_map"].items()}
    nat_date_map = {int(k): parse_date(v) for k, v in metadata["nat_date_map"].items()}
    
    return athletes_by_year, nat_place_map, nat_date_map

def load_nationals_races():
    """Load nationals race data"""
    with open("nationals_races.json", 'r') as f:
        nationals_list = json.load(f)
    return nationals_list

def build_athlete_snapshot_rows(athletes_by_year, nat_place_map, nat_date_map, nationals_list):
    """Build athlete snapshot statistics"""
    # First, flatten all race results from nationals
    all_race_rows = []
    for entry in nationals_list:
        race = entry['race_data']
        meet_name = race.get('meet_name')
        section = race.get('section')
        race_id = race.get('id')
        race_date = parse_date(race.get('date'))
        
        if is_track_meet(meet_name, section):
            continue
        
        xc_results = race.get('xc_results') or []
        for res in xc_results:
            runner = res.get('runner') or {}
            runner_id = runner.get('id')
            time_sec = res.get('time')
            place = res.get('place')
            
            all_race_rows.append({
                "athlete_id": runner_id,
                "race_id": race_id,
                "meet_date": race_date.isoformat() if race_date else None,
                "meet_name": meet_name,
                "race_section": section,
                "time_seconds": time_sec,
                "place": place,
                "raw_result": res
            })
    
    # Index by athlete
    races_by_athlete = defaultdict(list)
    for rr in all_race_rows:
        rid = rr.get('athlete_id')
        races_by_athlete[rid].append(rr)
    
    # Build snapshot rows
    athlete_rows = []
    for year in CONFIG["YEARS"]:
        nat_date = nat_date_map.get(year)
        athlete_ids = athletes_by_year.get(year, set())
        logging.info(f"Year {year}: {len(athlete_ids)} athletes")
        
        for aid in athlete_ids:
            all_races = races_by_athlete.get(aid, [])
            
            # Pre-nationals races
            if nat_date:
                pre_nat_races = [r for r in all_races if r['meet_date'] and parse_date(r['meet_date']) < nat_date]
            else:
                pre_nat_races = all_races
            
            # Season 8k races
            season_8k = [(r, parse_date(r['meet_date'])) for r in pre_nat_races 
                        if is_8k_distance(r.get('race_section') or "") 
                        and parse_date(r.get('meet_date')) 
                        and parse_date(r.get('meet_date')).year == year]
            
            # Lifetime 8k PR
            pr_time = None
            all_8k = [(r, parse_date(r['meet_date'])) for r in pre_nat_races 
                     if is_8k_distance(r.get('race_section') or "")]
            if all_8k:
                times = [float(x[0]['time_seconds']) for x in all_8k if x[0]['time_seconds'] is not None]
                if times:
                    pr_time = float(np.nanmin(times))
            
            # Season record
            sr_time = None
            if season_8k:
                times_s = [float(x[0]['time_seconds']) for x in season_8k if x[0]['time_seconds'] is not None]
                if times_s:
                    sr_time = float(np.nanmin(times_s))
            
            # Consistency (standard deviation of season 8k times)
            consistency = None
            if season_8k:
                times_s = np.array([float(x[0]['time_seconds']) for x in season_8k if x[0]['time_seconds'] is not None])
                if times_s.size >= 2:
                    consistency = float(np.std(times_s, ddof=0))
            
            # Days since season PR
            days_since_season_pr = None
            if sr_time is not None and nat_date is not None:
                matches = [x for x in season_8k if x[0]['time_seconds'] is not None and float(x[0]['time_seconds']) == sr_time]
                if matches:
                    pr_dates = [m[1] for m in matches if m[1] is not None]
                    if pr_dates:
                        best_date = max(pr_dates)
                        days_since_season_pr = (nat_date - best_date).days
            
            # All-American status
            nat_place = nat_place_map.get((year, aid))
            all_american = 1 if (nat_place is not None and isinstance(nat_place, int) and nat_place <= 40) else 0
            
            # Athlete info from sample race
            athlete_name = ""
            athlete_class = ""
            school = ""
            if all_races and isinstance(all_races[0].get('raw_result'), dict):
                rr = all_races[0]['raw_result']
                runner = rr.get('runner') or {}
                firstname = runner.get('firstname') or ""
                lastname = runner.get('lastname') or ""
                athlete_name = (firstname + " " + lastname).strip()
                athlete_class = runner.get('year_in_school') or ""
                team = runner.get('team') or {}
                school = team.get('name') or ""
            
            # Number of races
            num_races_run = len([r for r in pre_nat_races if parse_date(r['meet_date']) and parse_date(r['meet_date']).year == year])
            
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

def build_race_rows(athletes_by_year, nationals_list):
    """Build race results for included athletes"""
    included_athletes = set()
    for year in CONFIG["YEARS"]:
        included_athletes.update(athletes_by_year.get(year, set()))
    
    race_rows = []
    for entry in nationals_list:
        race = entry['race_data']
        meet_name = race.get('meet_name')
        section = race.get('section')
        race_date = parse_date(race.get('date'))
        
        if is_track_meet(meet_name, section):
            continue
        
        xc_results = race.get('xc_results') or []
        for res in xc_results:
            runner = res.get('runner') or {}
            runner_id = runner.get('id')
            
            if runner_id not in included_athletes:
                continue
            
            race_rows.append({
                "Athlete ID": runner_id,
                "Meet Date": race_date.isoformat() if race_date else None,
                "Meet Name": meet_name,
                "Race Distance": section or "",
                "Time": res.get('time') if res.get('time') is not None else CONFIG['MISSING_NUMERIC'],
                "Place": res.get('place') if res.get('place') is not None else CONFIG['MISSING_NUMERIC']
            })
    
    return race_rows

def main():
    logging.info("Loading metadata...")
    athletes_by_year, nat_place_map, nat_date_map = load_all_metadata()
    
    logging.info("Loading nationals races...")
    nationals_list = load_nationals_races()
    
    logging.info("Building athlete snapshots...")
    athlete_rows = build_athlete_snapshot_rows(athletes_by_year, nat_place_map, nat_date_map, nationals_list)
    
    logging.info("Building race results...")
    race_rows = build_race_rows(athletes_by_year, nationals_list)
    
    # Write CSVs
    athletes_df = pd.DataFrame(athlete_rows)
    races_df = pd.DataFrame(race_rows)
    
    athletes_df.to_csv("athletes.csv", index=False)
    races_df.to_csv("races.csv", index=False)
    
    logging.info(f"Wrote athletes.csv ({len(athletes_df)} rows) and races.csv ({len(races_df)} rows).")

if __name__ == "__main__":
    main()