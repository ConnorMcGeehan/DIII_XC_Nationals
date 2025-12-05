#!/usr/bin/env python3
"""
step1_fetch_nationals.py

Fetches all races from API and identifies 2024 nationals races only.
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
            time.sleep(CONFIG["REQUEST_SLEEP"])
    
    logging.info(f"Fetched total {len(races)} races (raw).")
    return races

def find_2024_nationals(races):
    """Filter to only 2024 nationals races"""
    target_year = 2024
    nationals_races = []
    target = CONFIG["NATIONALS_MEET_NAME"]
    
    # Track potential matches for debugging
    potential_matches = []
    
    for r in races:
        # Only men's races
        if (r.get('sex') or '').upper() != 'M':
            continue
        
        # Check date is 2024
        rd = parse_date(r.get('date'))
        if not rd or rd.year != target_year:
            continue
        
        # Check meet name
        name = r.get('meet_name') or ''
        cmp_name = name.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else name
        cmp_target = target.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else target
        
        # Track potential nationals for debugging
        if 'ncaa' in name.lower() and 'cross country' in name.lower():
            potential_matches.append(name)
        
        if cmp_name.strip() == cmp_target.strip():
            nationals_races.append(r)
    
    # Log results
    if nationals_races:
        logging.info(f"Found {len(nationals_races)} nationals races for 2024")
    else:
        logging.warning(f"No 2024 nationals races found with exact name: '{target}'")
        if potential_matches:
            logging.info(f"Found {len(potential_matches)} potential 2024 NCAA XC meets:")
            for name in set(potential_matches):
                logging.info(f"  - '{name}'")
    
    return nationals_races

def save_nationals_data(nationals_races, output_file="nationals_races.json"):
    """Save nationals race data to JSON file"""
    nationals_list = []
    for race in nationals_races:
        nationals_list.append({
            "year": 2024,
            "race_data": race
        })
    
    with open(output_file, 'w') as f:
        json.dump(nationals_list, f, indent=2, default=str)
    
    logging.info(f"Saved {len(nationals_list)} nationals races to {output_file}")

def main():
    logging.info("Fetching 2024 nationals races only...")
    races = fetch_all_races()
    nationals_races = find_2024_nationals(races)
    
    if not nationals_races:
        logging.error("No 2024 nationals races found! Check your CONFIG settings.")
        logging.error(f"Looking for meet name: '{CONFIG['NATIONALS_MEET_NAME']}'")
        logging.error(f"Case insensitive: {CONFIG['NATIONALS_CASE_INSENSITIVE']}")
    else:
        save_nationals_data(nationals_races)

if __name__ == "__main__":
    main()