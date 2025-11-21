#!/usr/bin/env python3
"""
step1_fetch_nationals.py

Fetches all races from API and identifies nationals races.
Outputs: nationals_races.json
"""

import requests
import json
import logging
import time
from dateutil import parser as dateparser
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

def fetch_all_races():
    """Fetch all races from API (paginated)"""
    races = []
    url = CONFIG["BASE_URL"] + CONFIG["RACE_ENDPOINT"]
    logging.info("Fetching race pages (paginated)...")
    
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
            #logging.info(f"Fetched {len(races)} races so far...")
            time.sleep(CONFIG["REQUEST_SLEEP"])
    
    logging.info(f"Fetched total {len(races)} races (raw).")
    return races

def find_nationals_races(races):
    """Filter to only nationals races for configured years"""
    nationals_by_year = {y: [] for y in CONFIG["YEARS"]}
    target = CONFIG["NATIONALS_MEET_NAME"]
    
    for r in races:
        if (r.get('sex') or '').upper() != 'M':
            continue
        
        name = r.get('meet_name') or ''
        cmp_name = name.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else name
        cmp_target = target.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else target
        
        if cmp_name.strip() == cmp_target.strip():
            rd = parse_date(r.get('date'))
            if rd and rd.year in CONFIG["YEARS"]:
                nationals_by_year[rd.year].append(r)
    
    for y in CONFIG["YEARS"]:
        if nationals_by_year[y]:
            logging.info(f"Year {y}: Found {len(nationals_by_year[y])} nationals races")
        else:
            logging.warning(f"Year {y}: No nationals races found")
    
    return nationals_by_year

def save_nationals_data(nationals_by_year, output_file="nationals_races.json"):
    """Save nationals race data to JSON file"""
    nationals_list = []
    for year, races in nationals_by_year.items():
        for race in races:
            nationals_list.append({
                "year": year,
                "race_data": race
            })
    
    with open(output_file, 'w') as f:
        json.dump(nationals_list, f, indent=2, default=str)
    
    logging.info(f"Saved {len(nationals_list)} nationals races to {output_file}")

def main():
    races = fetch_all_races()
    nationals_by_year = find_nationals_races(races)
    save_nationals_data(nationals_by_year)

if __name__ == "__main__":
    main()