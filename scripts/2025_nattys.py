#!/usr/bin/env python3
"""
Fetch 2025 D3 National Championship data and compile athlete statistics.
Outputs: athletes_data_2025.csv
"""

import requests
import json
import logging
import time
from datetime import datetime
from collections import defaultdict
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Configuration
CONFIG = {
    "BASE_URL": "https://c03mmwsf5i.execute-api.us-east-2.amazonaws.com/production/api_ranking/",
    "RACE_ENDPOINT": "race_page",
    "RUNNER_ENDPOINT": "xc_runner/",
    "REQUEST_HEADERS": {"User-Agent": "Mozilla/5.0"},
    "REQUEST_SLEEP": 0.5,
    "NATIONALS_MEET_NAME": "NCAA Division III Cross Country Championships",
    "NATIONALS_CASE_INSENSITIVE": True,
    "YEAR": 2025,
    "TRACK_KEYWORDS": ["track", "indoor", "outdoor", "stadium"],
    "MISSING_NUMERIC": -9999
}

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
    if not dstr:
        return None
    try:
        return datetime.fromisoformat(str(dstr).split('T')[0]).date()
    except Exception:
        try:
            return datetime.strptime(str(dstr), "%Y-%m-%d").date()
        except Exception:
            return None

def fetch_all_races():
    """Fetch all races from API (paginated)"""
    races = []
    url = CONFIG["BASE_URL"] + CONFIG["RACE_ENDPOINT"]
    logging.info("Fetching race pages...")
    
    while url:
        data = safe_get_json(url)
        if data is None:
            break
        
        if isinstance(data, dict) and 'results' in data:
            page_list = data['results']
            races.extend(page_list)
            url = data.get('next')
        elif isinstance(data, list):
            races.extend(data)
            url = None
        else:
            found = False
            for v in data.values():
                if isinstance(v, list):
                    races.extend(v)
                    found = True
                    break
            if not found:
                break
            url = None
        
        if url:
            time.sleep(CONFIG["REQUEST_SLEEP"])
    
    logging.info(f"Fetched {len(races)} total races")
    return races

def find_nationals_race(races, year):
    """Find the nationals race for the specified year"""
    target = CONFIG["NATIONALS_MEET_NAME"]
    
    for r in races:
        if (r.get('sex') or '').upper() != 'M':
            continue
        
        name = r.get('meet_name') or ''
        cmp_name = name.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else name
        cmp_target = target.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else target
        
        if cmp_name.strip() == cmp_target.strip():
            rd = parse_date(r.get('date'))
            if rd and rd.year == year:
                logging.info(f"Found {year} nationals race on {rd}")
                return r, rd
    
    logging.warning(f"No nationals race found for {year}")
    return None, None

def extract_athletes_from_nationals(nationals_race):
    """Extract athlete IDs from nationals race"""
    athletes = set()
    nat_place_map = {}
    athlete_info = {}
    
    for res in (nationals_race.get('xc_results') or []):
        runner = res.get('runner') or {}
        rid = runner.get('id')
        if rid is not None:
            athletes.add(rid)
            
            place = res.get('place')
            if place is not None:
                nat_place_map[rid] = place
            
            if rid not in athlete_info:
                firstname = runner.get('firstname') or ""
                lastname = runner.get('lastname') or ""
                athlete_info[rid] = {
                    "name": (firstname + " " + lastname).strip(),
                    "year_in_school": runner.get('year_in_school') or "",
                    "school": (runner.get('team') or {}).get('name') or ""
                }
    
    logging.info(f"Extracted {len(athletes)} athletes from nationals")
    return athletes, nat_place_map, athlete_info

def fetch_athlete_race_history(athlete_id):
    """Fetch complete race history for a single athlete"""
    url = CONFIG["BASE_URL"] + CONFIG["RUNNER_ENDPOINT"] + str(athlete_id)
    data = safe_get_json(url)
    time.sleep(CONFIG["REQUEST_SLEEP"])
    return data

def looks_like_8k(section):
    """Check if section looks like an 8k race"""
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
    """Remove duplicate performances"""
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
    """Compute lifetime PR before cutoff date"""
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
    """Compute season statistics"""
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
        filtered = []
        for p in perfs:
            if nat_date is not None and p['date'] is not None:
                if p['date'] >= nat_date:
                    continue
            filtered.append(p)
        season_perfs.extend(filtered)

    season_perfs = dedupe_performances(season_perfs)
    num_races = len(season_perfs)

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

def main():
    year = CONFIG["YEAR"]
    
    # Step 1: Find nationals race
    logging.info(f"Step 1: Fetching races and finding {year} nationals...")
    all_races = fetch_all_races()
    nationals_race, nat_date = find_nationals_race(all_races, year)
    
    if not nationals_race:
        logging.error(f"Could not find {year} nationals race. Exiting.")
        return
    
    # Step 2: Extract athletes
    logging.info("Step 2: Extracting athletes from nationals...")
    athletes, nat_place_map, athlete_info = extract_athletes_from_nationals(nationals_race)
    
    # Step 3: Fetch athlete histories
    logging.info(f"Step 3: Fetching race history for {len(athletes)} athletes...")
    athlete_histories = {}
    for i, athlete_id in enumerate(sorted(athletes)):
        if (i + 1) % 50 == 0:
            logging.info(f"Fetched {i + 1}/{len(athletes)} athletes...")
        
        history = fetch_athlete_race_history(athlete_id)
        if history:
            athlete_histories[athlete_id] = history
    
    # Step 4: Compile data
    logging.info("Step 4: Compiling athlete statistics...")
    rows = []
    
    for aid in sorted(athletes):
        history = athlete_histories.get(aid)
        if not history:
            logging.warning(f"No history for athlete {aid}; skipping")
            continue

        pr_time = gather_lifetime_pr_before_date(history, nat_date)
        season_stats = gather_season_stats(history, year, nat_date)

        info = athlete_info.get(aid, {})
        athlete_name = info.get('name') or (f"{history.get('firstname','')} {history.get('lastname','')}".strip())
        athlete_class = info.get('year_in_school') or history.get('year_in_school') or ''
        school = info.get('school') or (history.get('team') or {}).get('name') or ''

        nat_place = nat_place_map.get(aid)
        all_american = 1 if (isinstance(nat_place, int) and nat_place <= 40) else 0

        def nn(x):
            return CONFIG['MISSING_NUMERIC'] if x is None else x

        row = {
            'Athlete ID': aid,
            'Year': year,
            'Athlete Name': athlete_name,
            'Athlete Class': athlete_class,
            'School': school,
            'Number of Races Run': nn(season_stats['num_races']),
            'Personal Record': nn(pr_time),
            'Season Record': nn(season_stats['sr_time']),
            'Consistency': nn(season_stats['consistency']),
            'Days since Season PR': nn(season_stats['days_since_season_pr']),
            'All-American': all_american
        }
        rows.append(row)

    # Step 5: Save to CSV
    df = pd.DataFrame(rows)
    output_file = f"athletes_data_{year}.csv"
    df.to_csv(output_file, index=False)
    logging.info(f"✓ Wrote {output_file} with {len(df)} rows")
    print(f"\nSuccess! Data saved to: {output_file}")
    print(f"Total athletes: {len(df)}")
    print(f"All-Americans: {df['All-American'].sum()}")

if __name__ == "__main__":
    main()