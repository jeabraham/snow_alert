# tests/test_fetch.py

import pytest
from datetime import datetime
from fetch import get_snow_data, fetch_html, parse_snow_html

NOAA_URL = "https://www.nwrfc.noaa.gov/snow/snowplot.cgi?SUNQ1="

def test_fetch_html_live():
    html = fetch_html(NOAA_URL)
    assert isinstance(html, str)
    assert "<html" in html.lower()

def test_parse_snow_html_from_fixture():
    # Use a local saved page to keep parsing test deterministic
    fixture_path = "data/snowplot.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        html = f.read()

    data = parse_snow_html(html)

    assert isinstance(data, dict)

    # New expected keys from parse_snow_html
    expected_keys = [
        "swe_change_6h_in",
        "swe_change_12h_in",
        "swe_change_24h_in",
        "swe_change_48h_in",
        "swe_change_1w_in",
    ]
    for key in expected_keys:
        assert key in data, f"missing key: {key}"
        assert isinstance(data[key], (int, float)), f"{key} should be numeric"

def test_fetch_and_parse_live():
    # Fetch live HTML, then parse it end-to-end
    html = fetch_html(NOAA_URL)
    assert isinstance(html, str)
    assert "<html" in html.lower()

    data = parse_snow_html(html)
    assert isinstance(data, dict)

    expected_keys = [
        "swe_change_6h_in",
        "swe_change_12h_in",
        "swe_change_24h_in",
        "swe_change_48h_in",
        "swe_change_1w_in",
    ]
    for key in expected_keys:
        assert key in data, f"missing key: {key}"
        assert isinstance(data[key], (int, float)), f"{key} should be numeric"
