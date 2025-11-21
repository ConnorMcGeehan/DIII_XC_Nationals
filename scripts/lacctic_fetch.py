#!/usr/bin/env python3
"""
lacctic_fetch.py

Fetches cross-country results from the LACCTiC API and writes two CSVs:
 - athletes.csv  : one row per athlete per nationals year (2021-2024) with season snapshot before nationals
 - races.csv     : all men's race results for those athletes (all distances), excluding track meets

CONFIG section below: edit BASE_URL or REQUEST_HEADERS if your API needs an API key.
"""

import requests
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from dateutil import parser as dateparser
import time
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# ----------------------
# CONFIG - edit if needed
# ----------------------
CONFIG = {
    "BASE_URL": "https://c03mmwsf5i.execute-api.us-east-2.amazonaws.com/production/api_ranking",
    "RACE_ENDPOINT": "/race_page/",
    "RUNNER_ENDPOINT": "/runner_page/",
    "YEARS": [2024],
    # Exact nationals meet name to match per your instruction
    "NATIONALS_MEET_NAME": "NCAA Division III Cross Country Championships",
    # Nationals rule: match exact string in meet_name (case sensitive or insensitive)
    "NATIONALS_CASE_INSENSITIVE": True,
    # Exclude track meets by detecting these keywords in meet_name or section
    "TRACK_KEYWORDS": ["track", "indoor", "outdoor", "stadium", "meters", "meter", "m "],
    # Rate limit sleeps
    "REQUEST_SLEEP": 0.15,
    # Headers - put API key here if needed. e.g. {"Authorization": "Bearer TOKEN"}
    "REQUEST_HEADERS": {
        # "Authorization": "Bearer YOUR_TOKEN"
    },
    # How to represent missing numeric values in CSV
    "MISSING_NUMERIC": "NA"
}

# ----------------------
# Helper functions
# ----------------------

def safe_get_json(url, params=None, max_tries=3):
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
    if dstr is None:
        return None
    try:
        return dateparser.parse(dstr).date()
    except Exception:
        return None

def is_track_meet(meet_name, section):
    name = (meet_name or "").lower()
    sec = (section or "").lower()
    for kw in CONFIG["TRACK_KEYWORDS"]:
        if kw in name or kw in sec:
            # '5k' or '8k' often contain 'k' which is fine; but 'meters' likely indicates track
            # We'll treat 'meters' and 'meter' and 'indoor/outdoor/track' as track indicators.
            if kw.strip() in ("meters", "meter", "m"):
                return True
            if kw.strip() in ("track", "indoor", "outdoor", "stadium"):
                return True
    return False

def extract_distance_from_section(section):
    """
    Try to extract distance string like '8k', '10k', '5k', or numeric meters from the 'section' text.
    Returns a normalized string like '8k' or '10k' or None.
    """
    if not section:
        return None
    s = section.lower()
    # Common patterns: '(8k)', '8k', '8k run', '(10k)', '5000 m' etc.
    # First look for '8k', '10k', '5k' explicitly
    for d in ['8k', '10k', '5k', '6k', '6.0k']:
        if d in s:
            return d
    # Look for patterns like '(8k)' or '(10k)' or '8k' anywhere
    import re
    m = re.search(r'(\d{1,2})\s*k', s)
    if m:
        return f"{m.group(1)}k"
    # Look for meters like '5000' or '10000'
    m2 = re.search(r'(\d{4,5})\s*m', s)
    if m2:
        val = int(m2.group(1))
        if 7000 <= val <= 9000:
            return "8k"
        elif 4000 <= val <= 6000:
            return "5k"
        elif val >= 9000:
            return "10k"
    return None

def is_8k_distance(dist_str):
    if not dist_str:
        return False
    return dist_str.lower().startswith('8')

# ----------------------
# Pipeline
# ----------------------

def fetch_all_races():
    races = []
    url = CONFIG["BASE_URL"] + CONFIG["RACE_ENDPOINT"]
    params = {
        "meet_name": CONFIG["NATIONALS_MEET_NAME"]
    }
    logging.info("Fetching race pages (paginated)...")
    while url:
        data = safe_get = safe_get_json(url, params=params)
        if data is None:
            break
        # common API wraps list in 'results'
        if isinstance(data, dict) and 'results' in data:
            page_list = data['results']
            races.extend(page_list)
            url = data.get('next')
        elif isinstance(data, list):
            races.extend(data)
            # no pagination meta — break
            url = None
        else:
            # find first list value inside dict
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
            logging.info(f"Next page -> {url}")
            time.sleep(CONFIG["REQUEST_SLEEP"])
    logging.info(f"Fetched total {len(races)} races (raw).")
    return races

def build_race_result_rows(races):
    """
    Build a flat list of race result rows from race_page entries.
    Each race in race_page contains 'xc_results' which are result objects with runner info.
    """
    rows = []
    for r in races:
        # skip if not men's meet (we only want men's races in races.csv)
        sex = r.get('sex')
        if sex is not None and str(sex).upper() != 'M':
            continue
        meet_name = r.get('meet_name')
        section = r.get('section')
        # skip track meets entirely
        if is_track_meet(meet_name, section):
            continue
        race_id = r.get('id')
        race_date = parse_date(r.get('date'))
        dist = extract_distance_from_section(section)
        xc_results = r.get('xc_results') or []
        for res in xc_results:
            runner = res.get('runner') or {}
            runner_id = runner.get('id')
            time_sec = res.get('time')  # race_page uses seconds already in examples
            place = res.get('place')
            rows.append({
                "athlete_id": runner_id,
                "race_id": race_id,
                "meet_date": race_date.isoformat() if race_date else None,
                "meet_name": meet_name,
                "race_section": section,
                "race_distance": dist,
                "time_seconds": time_sec,
                "place": place,
                "raw_result": res
            })
    return rows

def find_nationals_races(races):
    """
    Return dict year -> list of nationals race records (race dicts).
    Match exact meet name (case insensitive if configured) and men's sex and years in CONFIG['YEARS'].
    """
    nationals_by_year = {y: [] for y in CONFIG["YEARS"]}
    target = CONFIG["NATIONALS_MEET_NAME"]
    for r in races:
        # must be male
        if (r.get('sex') or '').upper() != 'M':
            continue
        name = r.get('meet_name') or ''
        cmp_name = name.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else name
        cmp_target = target.lower() if CONFIG["NATIONALS_CASE_INSENSITIVE"] else target
        if cmp_name.strip() == cmp_target.strip():
            # parse date and get year
            rd = parse_date(r.get('date'))
            if rd and rd.year in CONFIG["YEARS"]:
                nationals_by_year[rd.year].append(r)
            else:
                # if date missing, try to infer year from other fields or just add to all years (unlikely)
                # we'll be conservative and add only if date's year in YEARS
                pass
    for y in CONFIG["YEARS"]:
        if not nationals_by_year[y]:
            logging.warning(f"No nationals race found for year {y}. Make sure the exact meet name is correct and the race_page includes it.")
    return nationals_by_year

def collect_athletes_from_nationals(nationals_by_year):
    """
    Return mapping: year -> set of athlete_ids who ran nationals that year, and mapping for (year, athlete) -> place at nationals and nationals_date.
    """
    athletes_by_year = {y: set() for y in CONFIG["YEARS"]}
    nat_place_map = {}  # (year, athlete_id) -> place
    nat_date_map = {}   # year -> nationals date (if multiple nationals races in a year, take earliest)
    for y, races in nationals_by_year.items():
        dates = []
        for r in races:
            rd = parse_date(r.get('date'))
            if rd:
                dates.append(rd)
            # collect runner ids from xc_results
            for res in (r.get('xc_results') or []):
                runner = res.get('runner') or {}
                rid = runner.get('id')
                if rid is not None:
                    athletes_by_year[y].add(rid)
                    # store place at nationals (if duplicates, keep smallest - though duplicates shouldn't happen)
                    existing = nat_place_map.get((y, rid))
                    place = res.get('place')
                    if place is not None:
                        if existing is None or (isinstance(place, int) and place < existing):
                            nat_place_map[(y, rid)] = place
        if dates:
            nat_date_map[y] = min(dates)
    return athletes_by_year, nat_place_map, nat_date_map

def build_athlete_snapshot_rows(athlete_ids_by_year, nat_place_map, nat_date_map, race_rows):
    """
    For each athlete-year combination, compute the snapshot stats using races before nationals_date.
    race_rows: list of dicts produced by build_race_result_rows()
    Returns list of athlete-row dicts and a filtered list of race_rows to include in races.csv (only rows for included athletes).
    """
    # index race_rows by athlete id for quick lookup
    from collections import defaultdict
    races_by_athlete = defaultdict(list)
    for rr in race_rows:
        rid = rr.get('athlete_id')
        races_by_athlete[rid].append(rr)

    athlete_rows = []
    included_race_rows = []

    for year in CONFIG["YEARS"]:
        nat_date = nat_date_map.get(year)  # may be None
        athlete_ids = athlete_ids_by_year.get(year, set())
        logging.info(f"Year {year}: {len(athlete_ids)} athletes found at nationals.")
        for aid in athlete_ids:
            # gather all races for athlete with date < nat_date (or excluding nationals by race_id)
            all_races = races_by_athlete.get(aid, [])
            # save included race rows (for races.csv) for athletes of interest - but only men's and non-track already filtered
            # We'll filter to those with meet_date <= some reasonable bound (we keep all years but will filter to requested years later)
            for r in all_races:
                included_race_rows.append(r)

            # Filter before nationals for stats
            if nat_date:
                pre_nat_races = [r for r in all_races if r['meet_date'] and parse_date(r['meet_date']) < nat_date]
            else:
                # If nationals date unknown, exclude races that are nationals by exact meet name
                pre_nat_races = [r for r in all_races if not (r['meet_name'] and ((r['meet_name'].lower() == CONFIG['NATIONALS_MEET_NAME'].lower()) if CONFIG['NATIONALS_CASE_INSENSITIVE'] else r['meet_name'] == CONFIG['NATIONALS_MEET_NAME']))]

            # Among pre-nationals, compute:
            # - season races = those with race year == year
            season_races = []
            prev_all_races_8k = []
            for r in pre_nat_races:
                # parse date and year
                rd = parse_date(r['meet_date'])
                r_year = rd.year if rd else None
                # classify as 8k by race_distance
                if is_8k_distance(r.get('race_distance') or ""):
                    # include for PR/SR/consistency
                    prev_all_races_8k.append((r, rd))
                if r_year == year:
                    season_races.append(r)

            # season 8k races
            season_8k = [ (r, parse_date(r['meet_date'])) for r in pre_nat_races if is_8k_distance(r.get('race_distance') or "") and parse_date(r.get('meet_date')) and parse_date(r.get('meet_date')).year == year ]

            # compute PR lifetime before nationals: min time of prev_all_races_8k
            pr_time = None
            if prev_all_races_8k:
                times = [float(x[0]['time_seconds']) for x in prev_all_races_8k if x[0]['time_seconds'] is not None]
                if times:
                    pr_time = float(np.nanmin(times))

            # season record before nationals
            sr_time = None
            if season_8k:
                times_s = [float(x[0]['time_seconds']) for x in season_8k if x[0]['time_seconds'] is not None]
                if times_s:
                    sr_time = float(np.nanmin(times_s))

            # consistency: std dev of season 8k times (population std dev)
            consistency = None
            if season_8k:
                times_s = np.array([float(x[0]['time_seconds']) for x in season_8k if x[0]['time_seconds'] is not None])
                if times_s.size >= 2:
                    consistency = float(np.std(times_s, ddof=0))
                elif times_s.size == 1:
                    # as per instructions, if fewer than 2 valid 8k races, consistency = NA
                    consistency = None

            # days since season PR: difference between nationals date and the date of the season's fastest 8k
            days_since_season_pr = None
            if sr_time is not None and nat_date is not None:
                # find the race(s) in season_8k with that time
                matches = [x for x in season_8k if x[0]['time_seconds'] is not None and float(x[0]['time_seconds']) == sr_time]
                if matches:
                    # choose the latest date among matches (closest before nationals)
                    pr_dates = [m[1] for m in matches if m[1] is not None]
                    if pr_dates:
                        best_date = max(pr_dates)
                        days_since_season_pr = (nat_date - best_date).days

            # All-American: check place at nationals (nat_place_map)
            nat_place = nat_place_map.get((year, aid))
            all_american = 1 if (nat_place is not None and isinstance(nat_place, int) and nat_place <= 40) else 0

            # athlete name/class/school: try to get from raw_result if available
            athlete_name = ""
            athlete_class = ""
            school = ""
            # find any race row with this athlete to extract fields
            sample = None
            if all_races:
                sample = all_races[0]
            # raw_result runner info might include firstname lastname year_in_school and team
            if sample and isinstance(sample.get('raw_result'), dict):
                rr = sample['raw_result']
                runner = rr.get('runner') or {}
                firstname = runner.get('firstname') or ""
                lastname = runner.get('lastname') or ""
                athlete_name = (firstname + " " + lastname).strip() if (firstname or lastname) else ""
                athlete_class = runner.get('year_in_school') or runner.get('year') or ""
                team = runner.get('team') or {}
                school = team.get('name') or ""
            # fallback empty strings if not found

            # number of races run in season before nationals (count ALL distances but exclude track; only men's races already)
            num_races_run = len([r for r in pre_nat_races if parse_date(r['meet_date']) and parse_date(r['meet_date']).year == year])

            # prepare output row with NA for missing numeric fields per your choice
            def nn(v):
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

    # Deduplicate included_race_rows and filter to only athlete ids that we included
    included_athletes = set()
    for r in athlete_rows:
        included_athletes.add(r["Athlete ID"])
    filtered_race_rows = [r for r in included_race_rows if r.get('athlete_id') in included_athletes]

    # Normalize races rows for CSV: ensure columns match requested schema and convert missing numeric to NA
    out_race_rows = []
    for r in filtered_race_rows:
        out_race_rows.append({
            "Athlete ID": r.get('athlete_id'),
            "Meet Date": r.get('meet_date'),
            "Meet Name": r.get('meet_name'),
            "Race Distance": r.get('race_distance') or "",
            "Time": r.get('time_seconds') if r.get('time_seconds') is not None else CONFIG['MISSING_NUMERIC'],
            "Place": r.get('place') if r.get('place') is not None else CONFIG['MISSING_NUMERIC']
        })

    return athlete_rows, out_race_rows

# ----------------------
# Main execution
# ----------------------

def main():
    # 1) fetch all races (paginated)
    races = fetch_all_races()
    if not races:
        logging.error("No races fetched; aborting.")
        sys.exit(1)

    from collections import Counter
    meet_names = Counter([r.get('meet_name') for r in races])
    logging.info("Meet names found:")
    for name, count in meet_names.most_common(10):
        logging.info(f"  '{name}': {count} races")

    # 2) find nationals races for each year
    nationals_by_year = find_nationals_races(races)

    # 3) get athletes who ran nationals
    athletes_by_year, nat_place_map, nat_date_map = collect_athletes_from_nationals(nationals_by_year)

    # If there are no nationals detected at all, abort with warning
    any_nationals = any(len(v)>0 for v in athletes_by_year.values())
    if not any_nationals:
        logging.error("No nationals athletes detected for any year. Check nationals meet name and data availability.")
        # Still proceed but will produce empty CSVs
    # 4) build flat race_rows from races (only men's and excluding track)
    race_rows = build_race_result_rows(races)

    # 5) build athlete snapshots and filtered race rows for included athletes
    athlete_rows, out_race_rows = build_athlete_snapshot_rows(athletes_by_year, nat_place_map, nat_date_map, race_rows)

    # Convert to DataFrames and write CSVs
    athletes_df = pd.DataFrame(athlete_rows, columns=[
        "Athlete ID","Year","Athlete Name","Athlete Class","School",
        "Number of Races Run","Personal Record","Season Record","Consistency",
        "Days since Season PR","All-American"
    ])
    races_df = pd.DataFrame(out_race_rows, columns=[
        "Athlete ID","Meet Date","Meet Name","Race Distance","Time","Place"
    ])

    # Ensure NA formatting for missing numeric fields already applied. Save to disk.
    athletes_df.to_csv("athletes.csv", index=False)
    races_df.to_csv("races.csv", index=False)

    logging.info(f"Wrote athletes.csv ({len(athletes_df)} rows) and races.csv ({len(races_df)} rows).")

if __name__ == "__main__":
    main()
