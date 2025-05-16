from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import time
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Load token from config.json
with open("config.json") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG.get("token")
BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

STORAGE_FILE = "storage.json"

# Ensure persistent bay/belt store exists
if not os.path.exists(STORAGE_FILE):
    with open(STORAGE_FILE, "w") as f:
        json.dump({}, f)

def load_storage():
    with open(STORAGE_FILE) as f:
        return json.load(f)

def save_storage(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)

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

@app.route("/flights")
def get_flights():
    try:
        mode = request.args.get("mode", "arrivals")
        timestamp = request.args.get("ts")
        ts = int(timestamp) if timestamp else int(time.time())
        url = build_url(mode, ts)
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        data = res.json()

        flight_data = (
            data.get("result", {})
            .get("response", {})
            .get("airport", {})
            .get("pluginData", {})
            .get("schedule", {})
            .get(mode, {})
            .get("data", [])
        )

        storage = load_storage()
        today_str = datetime.now().strftime("%Y-%m-%d")

        flights = []
        for f in flight_data:
            fl = f.get("flight", {})
            fn = fl.get("identification", {}).get("number", {}).get("default", "")
            reg = fl.get("aircraft", {}).get("registration", "")
            from_airport = fl.get("airport", {}).get("origin", {}).get("code", {}).get("iata", "")
            to_airport = fl.get("airport", {}).get("destination", {}).get("code", {}).get("iata", "")
            eta = fl.get("time", {}).get("estimated", {}).get("arrival" if mode == "arrivals" else "departure", 0)
            std = fl.get("time", {}).get("scheduled", {}).get("arrival" if mode == "arrivals" else "departure", 0)
            status = fl.get("status", {}).get("text", "")

            key = f"{today_str}|{fn}"
            bay = storage.get(key, {}).get("bay", "")
            belt = storage.get(key, {}).get("belt", "")

            flights.append({
                "flight": fn,
                "reg": reg,
                "from": from_airport,
                "to": to_airport,
                "eta": eta,
                "std": std,
                "status": status,
                "bay": bay,
                "belt": belt
            })

        return jsonify(flights)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update", methods=["POST"])
def update_bay_belt():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        flight = data.get("flight")
        bay = data.get("bay")
        belt = data.get("belt")

        if username != "Aswin" or password != "admin":
            return jsonify({"error": "Unauthorized"}), 403

        today_str = datetime.now().strftime("%Y-%m-%d")
        key = f"{today_str}|{flight}"
        store = load_storage()
        store[key] = {"bay": bay, "belt": belt}
        save_storage(store)
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "AIX Flight Tracker API is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
