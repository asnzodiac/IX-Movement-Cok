from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import time
import os

app = Flask(__name__)
CORS(app)

# Load token from config.json
with open("config.json") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG.get("token")
BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def build_url(mode: str, timestamp: int) -> str:
    # Construct the FR24 API URL with params
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
        mode = request.args.get("mode", "arrivals")  # arrivals or departures
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

        flights = []
        for f in flight_data:
            fl = f.get("flight", {})
            flights.append({
                "flight": fl.get("identification", {}).get("number", {}).get("default", ""),
                "reg": fl.get("aircraft", {}).get("registration", ""),
                "from": fl.get("airport", {}).get("origin", {}).get("code", {}).get("iata", ""),
                "to": fl.get("airport", {}).get("destination", {}).get("code", {}).get("iata", ""),
                "eta": fl.get("time", {}).get("estimated", {}).get("arrival" if mode == "arrivals" else "departure", 0),
                "std": fl.get("time", {}).get("scheduled", {}).get("arrival" if mode == "arrivals" else "departure", 0),
                "status": fl.get("status", {}).get("text", "")
            })

        return jsonify(flights)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "AIX Flight Tracker API is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
