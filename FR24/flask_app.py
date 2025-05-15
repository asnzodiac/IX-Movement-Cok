from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app)

with open("config.json") as f:
    CONFIG = json.load(f)

BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
TOKEN = CONFIG["token"]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def build_url(mode, timestamp):
    return f"{BASE_URL}?code=COK&plugin[]=schedule&plugin-setting[schedule][mode]={mode}&plugin-setting[schedule][timestamp]={timestamp}&limit=100&page=1&token={TOKEN}"

@app.route("/flights")
def get_flights():
    mode = request.args.get("mode", "arrivals")
    timestamp = request.args.get("ts")
    try:
        ts = int(timestamp) if timestamp else int(__import__("time").time())
        res = requests.get(build_url(mode, ts), headers=HEADERS)
        data = res.json()
        flight_data = data.get("result", {}).get("response", {}).get("airport", {}).get("pluginData", {}).get("schedule", {}).get(mode, {}).get("data", [])
        
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
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)