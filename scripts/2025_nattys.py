#!/usr/bin/env python3
"""
fetch_and_process_2025_nationals.py

Fetches the 2025 NCAA Division III Cross Country Championships race data,
retrieves each athlete's complete race history, and processes it to generate
statistics (PR, SR, consistency, etc.) as of nationals (excluding nationals itself).
Outputs: 2025_results.csv
"""

import requests
import json
import logging
import time
import numpy as np
import pandas as pd
from datetime import datetime
from dateutil import parser as dateparser

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Configuration
CONFIG = {
    "BASE_URL": "https://c03mmwsf5i.execute-api.us-east-2.amazonaws.com/production",
    "RUNNER_ENDPOINT": "/api_ranking/runner_page/",
    "REQUEST_SLEEP": 0.1,
    "TRACK_KEYWORDS": ["track", "indoor", "outdoor", "stadium"],
    "MISSING_NUMERIC": -9999
}

def safe_get_json(url, max_tries=3):
    """Safely fetch JSON from API with retry logic"""
    for attempt in range(max_tries):
        try:
            r = requests.get(url, timeout=30)
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
    if not dstr:
        return None
    try:
        return dateparser.parse(dstr).date()
    except Exception:
        try:
            return datetime.fromisoformat(dstr).date()
        except Exception:
            try:
                return datetime.strptime(dstr, "%Y-%m-%d").date()
            except Exception:
                return None

def looks_like_8k(section):
    """Check if race section indicates 8k distance"""
    if not section:
        return False
    s = str(section).lower()
    return ("8k" in s) or ("8000" in s)

def extract_xc_performances_from_season(season_block):
    """Extract only XC performances from a season block"""
    out = []
    if not isinstance(season_block, dict):
        return out

    perfs = season_block.get('season_xc_performances')
    if not perfs or not isinstance(perfs, list):
        return out

    for p in perfs:
        time = p.get('time')
        place = p.get('place')
        race = p.get('race') if isinstance(p.get('race'), dict) else {}
        meet_name = race.get('meet_name') or race.get('meet') or race.get('name') or ""
        section = race.get('section') or p.get('section') or ""
        date = parse_date(race.get('date') if race.get('date') else p.get('date'))

        try:
            time_val = float(time) if time is not None else None
        except Exception:
            time_val = None

        out.append({
            'time': time_val,
            'date': date,
            'section': section,
            'meet_name': meet_name,
            'place': place
        })

    return out

def dedupe_performances(perf_list):
    """Remove duplicate performances (same date, section, time)"""
    seen = set()
    unique = []

    for p in perf_list:
        date_key = p['date'].isoformat() if p['date'] is not None else 'nodate'
        sec_key = ' '.join(str(p['section']).lower().split()) if p.get('section') else ''
        time_key = None if p['time'] is None else round(float(p['time']), 6)
        key = (date_key, sec_key, time_key)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique

def gather_lifetime_pr_before_date(history, cutoff_date):
    """Compute lifetime PR (min 8k time) before cutoff_date"""
    times = []
    season_ratings = history.get('season_ratings') if isinstance(history, dict) else None
    if not season_ratings:
        return None

    for season in season_ratings:
        perfs = extract_xc_performances_from_season(season)
        for p in perfs:
            if p['time'] is None:
                continue
            if not looks_like_8k(p['section']):
                continue
            if cutoff_date is not None and p['date'] is not None and not (p['date'] < cutoff_date):
                continue
            times.append(p['time'])

    if not times:
        return None
    return float(np.nanmin(times))

def gather_season_stats(history, nat_year, nat_date):
    """Compute season stats before nationals date"""
    season_ratings = history.get('season_ratings') if isinstance(history, dict) else None
    if not season_ratings:
        return {'num_races': 0, 'sr_time': None, 'consistency': None, 'days_since_season_pr': None}

    season_perfs = []
    for season in season_ratings:
        year_block = None
        if isinstance(season.get('season'), dict):
            year_block = season['season'].get('year')
        elif isinstance(season.get('season'), int):
            year_block = season.get('season')

        if year_block != nat_year:
            continue

        perfs = extract_xc_performances_from_season(season)
        # Only keep perfs strictly before nationals date
        filtered = []
        for p in perfs:
            if nat_date is not None and p['date'] is not None:
                if p['date'] >= nat_date:
                    continue
            filtered.append(p)
        season_perfs.extend(filtered)

    # Deduplicate season perfs
    season_perfs = dedupe_performances(season_perfs)

    # Number of races
    num_races = len(season_perfs)

    # Season 8k times and dates
    season_8k = [p for p in season_perfs if p['time'] is not None and looks_like_8k(p['section'])]
    sr_time = float(np.nanmin([p['time'] for p in season_8k])) if season_8k else None

    consistency = None
    if len(season_8k) >= 2:
        arr = np.array([p['time'] for p in season_8k], dtype=float)
        consistency = float(np.std(arr, ddof=0))

    days_since = None
    if sr_time is not None and nat_date is not None:
        candidates = [p['date'] for p in season_8k if p['time'] == sr_time and p['date'] is not None]
        if candidates:
            best_date = max(candidates)
            days_since = (nat_date - best_date).days

    return {
        'num_races': num_races,
        'sr_time': sr_time,
        'consistency': consistency,
        'days_since_season_pr': days_since
    }

def fetch_nationals_2025_race():
    """Fetch the 2025 NCAA Division III XC Championships race"""
    url = "https://c03mmwsf5i.execute-api.us-east-2.amazonaws.com/production/api_ranking/race_page/?page=2"
    
    logging.info(f"Fetching race data from: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch data: {e}")
        return None, None, None
    
    if 'results' not in data:
        logging.error("No 'results' field in API response")
        return None, None, None
    
    races = data['results']
    
    # Find the 2025 NCAA Division III Championships race
    target_race = None
    for race in races:
        meet_name = race.get('meet_name', '')
        date = race.get('date', '')
        sex = race.get('sex', '')
        
        if ('NCAA Division III Cross Country Championships' in meet_name and 
            sex == 'M' and 
            date and date.startswith('2025')):
            target_race = race
            break
    
    if not target_race:
        logging.error("Could not find 2025 NCAA Division III Championships race")
        return None, None, None
    
    logging.info(f"Found race: {target_race['meet_name']}")
    logging.info(f"Date: {target_race['date']}")
    
    nat_date = parse_date(target_race['date'])
    
    # Extract all runner IDs and places
    athletes = []
    xc_results = target_race.get('xc_results', [])
    
    for result in xc_results:
        runner = result.get('runner', {})
        runner_id = runner.get('id')
        
        if runner_id is not None:
            firstname = runner.get('firstname', '')
            lastname = runner.get('lastname', '')
            team = runner.get('team', {})
            
            athletes.append({
                'id': runner_id,
                'name': f"{firstname} {lastname}".strip(),
                'year_in_school': runner.get('year_in_school', ''),
                'school': team.get('name', ''),
                'place': result.get('place'),
                'nat_time': result.get('time')
            })
    
    logging.info(f"Extracted {len(athletes)} athletes")
    
    return athletes, nat_date, target_race

def fetch_athlete_race_history(athlete_id):
    """Fetch complete race history for a single athlete"""
    url = CONFIG["BASE_URL"] + CONFIG["RUNNER_ENDPOINT"] + str(athlete_id)
    data = safe_get_json(url)
    time.sleep(CONFIG["REQUEST_SLEEP"])
    return data

def process_athlete_data(athletes, nat_date):
    """Fetch histories and compute stats for all athletes"""
    rows = []
    
    logging.info(f"Fetching race history for {len(athletes)} athletes...")
    
    for i, athlete in enumerate(athletes):
        if (i + 1) % 50 == 0:
            logging.info(f"Processed {i + 1}/{len(athletes)} athletes...")
        
        athlete_id = athlete['id']
        history = fetch_athlete_race_history(athlete_id)
        
        if not history:
            logging.warning(f"Failed to fetch history for athlete {athlete_id}")
            continue
        
        # Compute PR (lifetime best 8k before nationals)
        pr_time = gather_lifetime_pr_before_date(history, nat_date)
        
        # Compute season stats (2025 season, before nationals)
        season_stats = gather_season_stats(history, 2025, nat_date)
        
        # Determine All-American status (top 40)
        place = athlete['place']
        all_american = 1 if (isinstance(place, int) and place <= 40) else 0
        
        def nn(x):
            return CONFIG['MISSING_NUMERIC'] if x is None else x
        
        row = {
            'Athlete ID': athlete_id,
            'Year': 2025,
            'Athlete Name': athlete['name'],
            'Athlete Class': athlete['year_in_school'],
            'School': athlete['school'],
            'Number of Races Run': nn(season_stats['num_races']),
            'Personal Record': nn(pr_time),
            'Season Record': nn(season_stats['sr_time']),
            'Consistency': nn(season_stats['consistency']),
            'Days since Season PR': nn(season_stats['days_since_season_pr']),
            'All-American': all_american,
            'Nationals Place': nn(place),
            'Nationals Time': nn(athlete['nat_time'])
        }
        rows.append(row)
    
    logging.info(f"Successfully processed {len(rows)} athletes")
    return rows

def main():
    # Fetch 2025 nationals race
    athletes, nat_date, race_data = fetch_nationals_2025_race()
    
    if not athletes:
        logging.error("Failed to fetch nationals race data")
        return
    
    # Process all athletes
    rows = process_athlete_data(athletes, nat_date)
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(rows)
    df.to_csv("2025_results.csv", index=False)
    
    logging.info("=" * 60)
    logging.info(f"✓ Successfully created 2025_results.csv")
    logging.info(f"  - {len(df)} athletes from 2025 NCAA DIII Championships")
    logging.info(f"  - Nationals date: {nat_date}")
    logging.info(f"  - All-Americans: {df['All-American'].sum()}")
    logging.info("=" * 60)

if __name__ == "__main__":
    main()