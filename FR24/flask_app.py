from flask import Flask, jsonify, request, abort
from flask_cors import CORS
import requests
import json
import time
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Load token
with open("config.json") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG["token"]
BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Persistent storage for bay and belt
STORAGE_FILE = "bay_belt_store.json"
if os.path.exists(STORAGE_FILE):
    with open(STORAGE_FILE, "r") as f:
        BAY_BELT_STORE = json.load(f)
else:
    BAY_BELT_STORE = {}

def save_storage():
    with open(STORAGE_FILE, "w") as f:
        json.dump(BAY_BELT_STORE, f)

def build_url(mode: str, timestamp: int) -> str:
    return (
        f"{BASE_URL}"
        f"?code=COK"
        f"&plugin[]=schedule"
        f"&plugin-setting[schedule][mode]={mode}"
        f"&plugin-setting[schedule][timestamp]={timestamp}"
        f"&limit=100&page=1"
        f"&token={TOKEN}"
    )

def get_today_key(flight_no, date):
    return f"{flight_no}_{date}"

@app.route("/flights")
def get_flights():
    try:
        mode = request.args.get("mode", "arrivals")
        timestamp = request.args.get("ts")
        ts = int(timestamp) if timestamp else int(time.time())

        res = requests.get(build_url(mode, ts), headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        flights_raw = (
            data.get("result", {})
            .get("response", {})
            .get("airport", {})
            .get("pluginData", {})
            .get("schedule", {})
            .get(mode, {})
            .get("data", [])
        )

        today = datetime.utcnow().strftime("%Y-%m-%d")
        flights = []
        for f in flights_raw:
            fl = f.get("flight", {})
            flight_no = fl.get("identification", {}).get("number", {}).get("default", "")
            reg = fl.get("aircraft", {}).get("registration", "")
            key = get_today_key(flight_no, today)
            extra = BAY_BELT_STORE.get(key, {"bay": "", "belt": ""})

            flights.append({
                "flight": flight_no,
                "reg": reg,
                "from": fl.get("airport", {}).get("origin", {}).get("code", {}).get("iata", ""),
                "to": fl.get("airport", {}).get("destination", {}).get("code", {}).get("iata", ""),
                "eta": fl.get("time", {}).get("estimated", {}).get("arrival" if mode == "arrivals" else "departure", 0),
                "std": fl.get("time", {}).get("scheduled", {}).get("arrival" if mode == "arrivals" else "departure", 0),
                "status": fl.get("status", {}).get("text", ""),
                "model": fl.get("aircraft", {}).get("model", {}).get("code", ""),
                "bay": extra.get("bay", ""),
                "belt": extra.get("belt", "")
            })

        return jsonify(flights)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update", methods=["POST"])
def update_bay_belt():
    auth = request.authorization
    if not auth or not (auth.username == "Aswin" and auth.password == "admin"):
        return abort(401)

    data = request.get_json()
    flight_no = data.get("flight")
    bay = data.get("bay", "")
    belt = data.get("belt", "")
    if not flight_no:
        return jsonify({"error": "Missing flight number"}), 400

    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = get_today_key(flight_no, today)
    BAY_BELT_STORE[key] = {"bay": bay, "belt": belt}
    save_storage()
    return jsonify({"success": True})

@app.route("/")
def home():
    return "AIX Flight Tracker API is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
