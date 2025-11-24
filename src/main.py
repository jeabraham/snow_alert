# src/main.py

import logging
import json
from pathlib import Path
from typing import Dict, Any, Tuple
import requests

import yaml  # requires PyYAML
from fetch import fetch_html, parse_snow_html

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def load_config(path: str = "config/snow-alert.yaml") -> Dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_latest_html(html: str, out_path: str = "data/snowplot.html") -> None:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    logger.info("Saved HTML to %s (%d bytes)", p, len(html))


def inches_from_config(cfg: Dict[str, Any], key_cm: str) -> float:
    # Convert a centimeters threshold to inches; default 0 if not present
    val_cm = float(cfg.get("threshold", {}).get(key_cm, 0.0))
    return val_cm / 2.54

def inches_from_cm(cm: float) -> float:
    try:
        return float(cm) / 2.54
    except Exception:
        return float("nan")


def evaluate_thresholds(cfg: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare parsed SWE changes to per-window thresholds.
    Returns: {"alert": bool, "reasons": [..], "metrics": {...}, "thresholds": {...}}
    """
    swe_cfg = (cfg.get("threshold", {}).get("swe_change_cm") or {})
    # thresholds (inches) per window
    th_in = {
        "h6": inches_from_cm(swe_cfg.get("h6", float("nan"))),
        "h12": inches_from_cm(swe_cfg.get("h12", float("nan"))),
        "h24": inches_from_cm(swe_cfg.get("h24", float("nan"))),
        "h48": inches_from_cm(swe_cfg.get("h48", float("nan"))),
        "w1": inches_from_cm(swe_cfg.get("w1", float("nan"))),
    }

    # parsed values
    vals = {
        "h6": float(parsed.get("swe_change_6h_in", float("nan"))),
        "h12": float(parsed.get("swe_change_12h_in", float("nan"))),
        "h24": float(parsed.get("swe_change_24h_in", float("nan"))),
        "h48": float(parsed.get("swe_change_48h_in", float("nan"))),
        "w1": float(parsed.get("swe_change_1w_in", float("nan"))),
    }

    def meets(v: float, t: float) -> Tuple[bool, str]:
        if v != v or t != t:  # NaN-safe
            return False, ""
        return (v >= t), f"{v:.2f} in >= {t:.2f} in"

    reasons = []
    windows = {"h6": "6h", "h12": "12h", "h24": "24h", "h48": "48h", "w1": "1w"}
    for k in ["h6", "h12", "h24", "h48", "w1"]:
        ok, msg = meets(vals[k], th_in[k])
        if ok:
            reasons.append(f"{windows[k]} SWE change {msg}")

    alert = len(reasons) > 0

    return {
        "alert": alert,
        "reasons": reasons,
        "metrics": {
            "swe_change_6h_in": vals["h6"],
            "swe_change_12h_in": vals["h12"],
            "swe_change_24h_in": vals["h24"],
            "swe_change_48h_in": vals["h48"],
            "swe_change_1w_in": vals["w1"],
        },
        "thresholds": {
            "swe_change_in": {
                "h6": th_in["h6"],
                "h12": th_in["h12"],
                "h24": th_in["h24"],
                "h48": th_in["h48"],
                "w1": th_in["w1"],
            }
        },
    }

def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None) -> None:
    try:
        resp = requests.post(url, json=payload, headers=headers or {}, timeout=10)
        resp.raise_for_status()
        logger.info("Notification POST to %s OK (status %s)", url, resp.status_code)
    except Exception as e:
        logger.error("Notification POST failed to %s: %s", url, e)

def notify(cfg: Dict[str, Any], result: Dict[str, Any]) -> None:
    """
    Notification dispatcher:
    - console
    - ifttt: uses notification.ifttt.{key,event}
    - hubitat: uses notification.hubitat.{url,token,device_id}
    - homekit: uses notification.homekit.{url,auth_token}
    """
    notif = cfg.get("notification", {}) or {}
    if not notif.get("enabled", True):
        logger.info("Notification disabled in config")
        return

    method = notif.get("method", "console")
    title = "Snow Alert" if result["alert"] else "Snow Update"
    body = {
        "alert": result["alert"],
        "reasons": result.get("reasons", []),
        "metrics": result.get("metrics", {}),
        "thresholds": result.get("thresholds", {}),
    }

    if method == "console":
        if result["alert"]:
            print(f"[ALERT] {', '.join(result.get('reasons', [])) or '(no reason)'}")
        else:
            print("[OK] No alert. Metrics:", json.dumps(result.get("metrics", {})))
        return

    if method == "ifttt":
        key = (notif.get("ifttt") or {}).get("key", "")
        event = (notif.get("ifttt") or {}).get("event", "snow_alert")
        if not key:
            logger.error("IFTTT key missing")
            return
        url = f"https://maker.ifttt.com/trigger/{event}/json/with/key/{key}"
        payload = {"value1": title, "value2": ", ".join(result.get("reasons", [])), "value3": json.dumps(body)}
        _post_json(url, payload)
        return

    if method == "hubitat":
        hub = notif.get("hubitat") or {}
        url = hub.get("url", "")
        if not url:
            logger.error("Hubitat url missing")
            return
        payload = {"title": title, "message": ", ".join(result.get("reasons", [])) or "No alert", "data": body}
        headers = {}
        token = hub.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        _post_json(url, payload, headers=headers)
        return

    if method == "homekit":
        hk = notif.get("homekit") or {}
        url = hk.get("url", "")
        if not url:
            logger.error("Homekit url missing")
            return
        headers = {}
        if hk.get("auth_token"):
            headers["Authorization"] = f"Bearer {hk['auth_token']}"
        payload = {"alert": result["alert"], "title": title, "message": ", ".join(result.get("reasons", [])), "data": body}
        _post_json(url, payload, headers=headers)
        return

    logger.warning("Unknown notification method: %s", method)
    # Fallback to console
    if result["alert"]:
        print(f"[ALERT] {', '.join(result.get('reasons', [])) or '(no reason)'}")
    else:
        print("[OK] No alert. Metrics:", json.dumps(result.get("metrics", {})))

def main() -> None:
    cfg = load_config("config/snow-alert.yaml")
    url = cfg.get("station", {}).get("sunshine_url")
    if not url:
        raise ValueError("Missing station.sunshine_url in config")

    logger.info("Downloading HTML from %s", url)
    html = fetch_html(url)
    save_latest_html(html, "data/snowplot.html")

    parsed = parse_snow_html(html)
    result = evaluate_thresholds(cfg, parsed)

    if result["alert"]:
        logger.info("Alert conditions met: %s", "; ".join(result["reasons"]))
    else:
        logger.info("No alert condition met")

    notify(cfg, result)


if __name__ == "__main__":
    main()
