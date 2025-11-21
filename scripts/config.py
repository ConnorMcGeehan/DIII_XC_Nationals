#!/usr/bin/env python3
"""
config.py - Shared configuration for all steps
"""

CONFIG = {
    "BASE_URL": "https://c03mmwsf5i.execute-api.us-east-2.amazonaws.com/production/api_ranking",
    "RACE_ENDPOINT": "/race_page/",
    "RUNNER_ENDPOINT": "/runner_page/",
    "YEARS": [2021, 2022, 2023, 2024],
    "NATIONALS_MEET_NAME": "NCAA Division III Cross Country Championships",
    "NATIONALS_CASE_INSENSITIVE": True,
    "TRACK_KEYWORDS": ["track", "indoor", "outdoor", "stadium", "meters", "meter", "m "],
    "REQUEST_SLEEP": 0.05,
    "REQUEST_HEADERS": {
        # Add API key here if needed: "Authorization": "Bearer YOUR_TOKEN"
    },
    "MISSING_NUMERIC": "NA"
}