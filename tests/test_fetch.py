# tests/test_fetch.py

import sys
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from fetch import get_snow_data
from datetime import datetime

NOAA_URL = "https://www.nwrfc.noaa.gov/snow/snowplot.cgi?SUNQ1="


def test_get_snow_data_live():
    """
    Live integration test – makes a real HTTP call.
    Good for development, but you might mark it 'manual' or 'external'
    if you begin running tests offline or in CI.
    """
    data = get_snow_data(NOAA_URL)

    # Structural checks
    assert isinstance(data, dict), "Expected result to be a dict"
    for key in ["snow_depth_in", "swe_change_24h_in", "timestamp"]:
        assert key in data, f"Missing key: {key}"

    # Type checks
    assert isinstance(data["snow_depth_in"], (int, float)), "snow_depth_in should be numeric"
    assert isinstance(data["swe_change_24h_in"], (int, float)), "swe_change_24h_in should be numeric"
    assert isinstance(data["timestamp"], datetime), "timestamp should be datetime"

    # Value sanity
    assert data["snow_depth_in"] >= 0, "Depth shouldn't be negative"
    assert -10 < data["swe_change_24h_in"] < 100, "Unlikely SWE change range – parser may be broken"

    print("\nLive NOAA data parsed:")
    print(data)
