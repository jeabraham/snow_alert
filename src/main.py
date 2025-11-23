
from fetch import get_snow_data
from process import evaluate_snow
from notify import send_alert
from config import load_config
import json, os

def main():
    cfg = load_config()
    station_data = get_snow_data(cfg["station"]["sunshine_url"])
    result = evaluate_snow(cfg, station_data)

    if result["alert"]:
        send_alert(result)

    # persist state (even if no alert, we still update)
    with open("data/last_state.json", "w") as f:
        json.dump(result["state"], f)

if __name__ == "__main__":
    main()
