#!/usr/bin/env python3
"""
Fixed step3_compile_data.py — improvements based on user feedback:

- PR is now computed *as of nationals* (min time among XC races with date < nationals date).
  This gives the athlete's best time up to the national meet for that year.
- Season counts and season stats use **only** `season_xc_performances` (track results excluded).
- Duplicate races (same date, normalized section, same time) are de-duplicated and counted once.
- Season record, consistency, days-since-PR exclude nationals itself (races with date >= nat_date).

Reads: /mnt/data/athlete_race_history.json (default)
Writes: athletes.csv
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

# Try to import CONFIG; fallback defaults
try:
    from config import CONFIG
except Exception:
    CONFIG = {
        "YEARS": [2021, 2022, 2023],
        "TRACK_KEYWORDS": ["track", "indoor", "outdoor", "stadium"],
        "MISSING_NUMERIC": -9999
    }

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

INPUT_PATH = "/mnt/data/athlete_race_history.json"
OUTPUT_CSV = "athletes.csv"


def parse_date(dstr):
    if not dstr:
        return None
    try:
        return datetime.fromisoformat(dstr).date()
    except Exception:
        try:
            return datetime.strptime(dstr, "%Y-%m-%d").date()
        except Exception:
            try:
                return datetime.fromisoformat(str(dstr).split('T')[0]).date()
            except Exception:
                return None


def looks_like_8k(section):
    if not section:
        return False
    s = str(section).lower()
    return ("8k" in s) or ("8000" in s)


def is_track_meet(meet_name, section):
    name = (meet_name or "").lower()
    sec = (section or "").lower()
    for kw in CONFIG.get("TRACK_KEYWORDS", []):
        kk = kw.lower()
        if kk in name or kk in sec:
            return True
    return False


def extract_xc_performances_from_season(season_block):
    """Extract only XC performances from a season block and normalize them.
    Return list of dicts with keys: time (float|None), date (date|None), section (str), meet_name (str), place
    """
    out = []
    if not isinstance(season_block, dict):
        return out

    perfs = season_block.get('season_xc_performances')
    if not perfs or not isinstance(perfs, list):
        return out

    for p in perfs:
        # Each p typically: {time, modern_tic, race_weight_sig, significant, race: {...}, place}
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
    """Remove duplicates defined as same date (or None), normalized section, and same time.
    Return list of unique performances preserving first occurrence order.
    """
    seen = set()
    unique = []

    for p in perf_list:
        date_key = p['date'].isoformat() if p['date'] is not None else 'nodate'
        # Normalize section: lowercase, collapse whitespace
        sec_key = ' '.join(str(p['section']).lower().split()) if p.get('section') else ''
        time_key = None if p['time'] is None else round(float(p['time']), 6)
        key = (date_key, sec_key, time_key)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def gather_lifetime_pr_before_date(history, cutoff_date):
    """Compute lifetime PR (min 8k time) across all seasons' XC performances with date < cutoff_date.
    If cutoff_date is None, consider all dates.
    Only include performances that look like 8k.
    """
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
                # Exclude races on/after the cutoff
                continue
            # If date missing and cutoff_date given, conservatively include it (user may want it)
            times.append(p['time'])

    if not times:
        return None
    return float(np.nanmin(times))


def gather_season_stats(history, nat_year, nat_date):
    """Return season-specific stats using only season_xc_performances in the nat_year and before nat_date.
    Returns dict: num_races, sr_time, consistency, days_since_season_pr
    """
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
        # Only keep perfs strictly before nationals date (if nat_date present)
        filtered = []
        for p in perfs:
            if nat_date is not None and p['date'] is not None:
                if p['date'] >= nat_date:
                    continue
            # If p['date'] is None and nat_date exists, we still include it for counts but not for date-based things
            filtered.append(p)
        season_perfs.extend(filtered)

    # Deduplicate season perfs
    season_perfs = dedupe_performances(season_perfs)

    # Number of races: count of season_perfs (XC only)
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
        # find most recent date among season_8k races that equal sr_time and have a date
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


def build_rows_from_json(input_path: str):
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"Input JSON not found at {input_path}")

    with p.open('r') as f:
        data = json.load(f)

    athletes_by_year = {int(k): set(v) for k, v in data.get('athletes_by_year', {}).items()}
    nat_place_map = {tuple(map(int, k.split(','))): v for k, v in data.get('nat_place_map', {}).items()}
    nat_date_map = {int(k): parse_date(v) for k, v in data.get('nat_date_map', {}).items()}
    athlete_info = {int(k): v for k, v in data.get('athlete_info', {}).items()}
    athlete_histories = {int(k): v for k, v in data.get('athlete_histories', {}).items()}

    rows = []

    for year in CONFIG.get('YEARS', [2021, 2022, 2023]):
        nat_date = nat_date_map.get(year)
        athlete_ids = athletes_by_year.get(year, set())
        logging.info(f"Processing year {year}: {len(athlete_ids)} athletes; nationals date = {nat_date}")

        for aid in sorted(athlete_ids):
            history = athlete_histories.get(aid)
            if not history:
                logging.warning(f"No history for athlete {aid}; skipping")
                continue

            # Lifetime PR as of nationals: min 8k time across all XC perfs with date < nat_date
            pr_time = gather_lifetime_pr_before_date(history, nat_date)

            # Season stats (only XC, deduped, before nationals): num_races, sr_time, consistency, days
            season_stats = gather_season_stats(history, year, nat_date)

            info = athlete_info.get(aid, {})
            athlete_name = info.get('name') or (f"{history.get('firstname','')} {history.get('lastname','')}".strip())
            athlete_class = info.get('year_in_school') or history.get('year_in_school') or ''
            school = info.get('school') or (history.get('team') or {}).get('name') or ''

            nat_place = nat_place_map.get((year, aid))
            all_american = 1 if (isinstance(nat_place, int) and nat_place <= 40) else 0

            def nn(x):
                return CONFIG.get('MISSING_NUMERIC', -9999) if x is None else x

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

    return rows


def main():
    rows = build_rows_from_json("athlete_race_history.json")
    df = pd.DataFrame(rows)
    df.to_csv("athletes_data.csv", index=False)
    logging.info(f"Wrote {OUTPUT_CSV} with {len(df)} rows")


if __name__ == '__main__':
    main()
