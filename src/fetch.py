# src/fetch.py
import logging
from datetime import datetime
from typing import Dict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def fetch_html(url: str, timeout: int = 10) -> str:
    """
    Retrieve raw HTML from the given URL.
    Raises requests.HTTPError on bad status.
    """
    logger.debug("Fetching URL: %s (timeout=%s)", url, timeout)
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        logger.debug("Fetched %d bytes from %s", len(resp.text or ""), url)
        return resp.text
    except requests.Timeout as e:
        logger.error("Timeout fetching %s: %s", url, e)
        raise
    except requests.HTTPError as e:
        logger.error("HTTP error fetching %s: %s", url, e)
        raise
    except requests.RequestException as e:
        logger.error("Request error fetching %s: %s", url, e)
        raise

def parse_snow_html(html: str) -> Dict[str, object]:
    """
    Parse NOAA snow plot HTML into structured data, including SWE changes.
    Returns:
        {
            "snow_depth_in": float,            # if you already parse it elsewhere
            "swe_change_6h_in": float,
            "swe_change_12h_in": float,
            "swe_change_24h_in": float,
            "swe_change_48h_in": float,
            "swe_change_1w_in": float,
            "timestamp": datetime,             # if you already parse it elsewhere
        }
    """
    if not html or not isinstance(html, str):
        logger.error("parse_snow_html received invalid HTML input (type=%s, len=%s)",
                     type(html).__name__, len(html) if isinstance(html, str) else "n/a")
        raise ValueError("Invalid HTML input")

    soup = BeautifulSoup(html, "html.parser")

    # Find the table with column headers containing "SWE Change"
    candidate_tables = soup.find_all("table")
    logger.debug("Found %d tables in document", len(candidate_tables))
    swe_table = None
    for idx, tbl in enumerate(candidate_tables):
        header_cells = tbl.find_all(["td", "th"])
        header_text = " ".join(h.get_text(" ", strip=True) for h in header_cells).lower()
        if "swe change" in header_text and ("6 hour" in header_text or "12 hour" in header_text):
            swe_table = tbl
            logger.debug("Selected SWE Change table at index %d", idx)
            break
    if not swe_table:
        logger.warning("SWE Change table not found using header scan")
        raise ValueError("SWE Change table not found")

    # First data row after the header row
    rows = swe_table.find_all("tr")
    logger.debug("SWE table rows=%d", len(rows))
    if len(rows) < 2:
        logger.warning("SWE Change table has no data rows")
        raise ValueError("SWE Change table has no data rows")

    # Find the first row that actually contains numeric cells (defensive if extra header rows appear)
    data_row = None
    for r in rows[1:]:
        tds = r.find_all("td")
        texts = [td.get_text(strip=True) for td in tds]
        if any(texts) and any(ch.isdigit() for txt in texts for ch in txt):
            data_row = r
            break

    if data_row is None:
        logger.warning("No numeric data row found in SWE Change table")
        raise ValueError("SWE Change table row missing numeric data")

    data_tds = data_row.find_all("td")
    logger.debug("SWE data row has %d cells", len(data_tds))
    if len(data_tds) < 5:
        logger.warning("SWE Change data row has %d cells, expected at least 5", len(data_tds))
        raise ValueError("SWE Change table row missing cells")

    def to_float(td, label: str) -> float:
        raw = td.get_text(strip=True)
        txt = raw.replace(",", "")
        try:
            val = float(txt)
            return val
        except ValueError:
            logger.info("Non-numeric value for %s: %r -> NaN", label, raw)
            return float("nan")

    labels = ["6h", "12h", "24h", "48h", "1w"]
    values = [to_float(td, labels[i]) for i, td in enumerate(data_tds[:5])]

    result: Dict[str, object] = {
        "swe_change_6h_in": values[0],
        "swe_change_12h_in": values[1],
        "swe_change_24h_in": values[2],
        "swe_change_48h_in": values[3],
        "swe_change_1w_in": values[4],
    }

    logger.debug(
        "Parsed SWE changes: 6h=%s, 12h=%s, 24h=%s, 48h=%s, 1w=%s",
        result["swe_change_6h_in"],
        result["swe_change_12h_in"],
        result["swe_change_24h_in"],
        result["swe_change_48h_in"],
        result["swe_change_1w_in"],
    )

    return result


def get_snow_data(url: str) -> Dict[str, object]:
    """
    Orchestrates fetching and parsing.
    """
    logger.info("Getting snow data from %s", url)
    html = fetch_html(url)
    data = parse_snow_html(html)
    logger.info("Parsed snow data keys: %s", sorted(list(data.keys())))
    return data
