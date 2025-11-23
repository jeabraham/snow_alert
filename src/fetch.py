# src/fetch.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime


def get_snow_data(url: str) -> dict:
    """
    Fetches the NOAA snow plot data for SUNQ1 station
    Returns:
        {
            "snow_depth_in": float,
            "swe_change_24h_in": float,
            "timestamp": datetime,
        }
    """
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # --- Parse latest row from the data table ---
    # Find the first row containing numeric snow data.
    # The table generally has headers before the first data row.
    table = soup.find("table")
    if not table:
        raise RuntimeError("No table found at NOAA page")

    rows = table.find_all("tr")
    data_row = None

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        # Look for numeric snow depth column (e.g. "6.46")
        if len(cols) >= 4:
            try:
                float(cols[3])  # column 3 = snow depth
                data_row = cols
                break
            except ValueError:
                pass

    if not data_row:
        raise RuntimeError("Could not find valid snow data row")

    # Indexing based on typical NOAA table:
    # Date | Time | SWE (in) | Depth (in) | Density | Prec to Date | Temp
    date_str = data_row[0]
    time_str = data_row[1]
    swe_in = float(data_row[2])
    depth_in = float(data_row[3])

    # Parse timestamp (NOAA uses PST but doesn't specify timezone shift explicitly)
    try:
        timestamp = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H%M")
    except ValueError:
        timestamp = datetime.utcnow()

    # --- Summary table with change values ---
    summary_table = soup.find_all("table")[-1]  # Typically last
    swe_changes = summary_table.find_all("td")[1:6]  # 6hr, 12hr, 24hr, 48hr, 1wk

    # Extract 24h SWE change
    try:
        swe_change_24h_in = float(swe_changes[2].get_text(strip=True))
    except Exception:
        swe_change_24h_in = 0.0

    return {
        "snow_depth_in": depth_in,
        "swe_change_24h_in": swe_change_24h_in,
        "timestamp": timestamp,
    }
