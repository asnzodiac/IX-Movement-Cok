from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests, time, json, os
from datetime import datetime

app = Flask(__name__)
CORS(app)

CONFIG = json.load(open("config.json"))
DATA_FILE = "bay_belt_data.json"
TOKEN = CONFIG["token"]
BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_bay_belt_data():
    with open(DATA_FILE) as f:
        return json.load(f)

def save_bay_belt_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_date_str(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

@app.route("/flights")
def get_flights():
    mode = request.args.get("mode", "arrivals")
    timestamp = int(request.args.get("ts", time.time()))
    res = requests.get(
        f"{BASE_URL}?code=COK&plugin[]=schedule&plugin-setting[schedule][mode]={mode}&plugin-setting[schedule][timestamp]={timestamp}&limit=100&page=1&token={TOKEN}",
        headers=HEADERS,
    )
    raw = res.json()
    data = raw.get("result", {}).get("response", {}).get("airport", {}).get("pluginData", {}).get("schedule", {}).get(mode, {}).get("data", [])
    
    bay_belt = load_bay_belt_data()
    flights = []

    for f in data:
        fl = f.get("flight", {})
        flight_no = fl.get("identification", {}).get("number", {}).get("default", "")
        reg = fl.get("aircraft", {}).get("registration", "")
        aircraft = fl.get("aircraft", {}).get("model", {}).get("text", "")
        origin = fl.get("airport", {}).get("origin", {}).get("code", {}).get("iata", "")
        dest = fl.get("airport", {}).get("destination", {}).get("code", {}).get("iata", "")
        eta = fl.get("time", {}).get("estimated", {}).get("arrival" if mode == "arrivals" else "departure", 0)
        std = fl.get("time", {}).get("scheduled", {}).get("arrival" if mode == "arrivals" else "departure", 0)
        status = fl.get("status", {}).get("text", "")

        key = f"{flight_no}_{get_date_str(std)}"
        entry = bay_belt.get(key, {"bay": "", "belt": ""})

        flights.append({
            "flight": flight_no,
            "reg": reg,
            "aircraft": aircraft,
            "from": origin,
            "to": dest,
            "eta": eta,
            "std": std,
            "status": status,
            "bay": entry.get("bay", ""),
            "belt": entry.get("belt", "")
        })

    return jsonify(flights)

@app.route("/update-baybelt", methods=["POST"])
def update_bay_belt():
    auth = request.authorization
    if not auth or auth.username != "Aswin" or auth.password != "admin":
        return jsonify({"error": "Unauthorized"}), 401
    
    updates = request.json
    data = load_bay_belt_data()

    for entry in updates:
        key = f"{entry['flight']}_{get_date_str(entry['std'])}"
        data[key] = {
            "bay": entry.get("bay", ""),
            "belt": entry.get("belt", "")
        }

    save_bay_belt_data(data)
    return jsonify({"status": "success"})

@app.route("/")
def home():
    return "Flight Tracker API is running"
