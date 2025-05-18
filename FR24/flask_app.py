from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import time
import os

app = Flask(__name__)
CORS(app)

with open("config.json") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG["token"]
BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

@app.route("/flights")
def get_flights():
    mode = request.args.get("mode", "arrivals")
    ts = int(request.args.get("ts", time.time()))
    url = f"{BASE_URL}?code=COK&plugin[]=schedule&plugin-setting[schedule][mode]={mode}&plugin-setting[schedule][timestamp]={ts}&limit=100&page=1&token={TOKEN}"
    res = requests.get(url, headers=HEADERS)
    flights = res.json().get("result", {}).get("response", {}).get("airport", {}).get("pluginData", {}).get("schedule", {}).get(mode, {}).get("data", [])
    out = []
    for f in flights:
        fl = f.get("flight", {})
        out.append({
            "flight": fl.get("identification", {}).get("number", {}).get("default", ""),
            "reg": fl.get("aircraft", {}).get("registration", ""),
            "from": fl.get("airport", {}).get("origin", {}).get("code", {}).get("iata", ""),
            "to": fl.get("airport", {}).get("destination", {}).get("code", {}).get("iata", ""),
            "eta": fl.get("time", {}).get("estimated", {}).get("arrival" if mode == "arrivals" else "departure", 0),
            "std": fl.get("time", {}).get("scheduled", {}).get("arrival" if mode == "arrivals" else "departure", 0),
            "status": fl.get("status", {}).get("text", ""),
            "model": fl.get("aircraft", {}).get("model", {}).get("code", "")
        })
    return jsonify(out)

@app.route("/search-atd")
def search_atd():
    flight = request.args.get("flight", "")
    if not flight:
        return jsonify({"error": "Missing flight number"})
    try:
        api_key = "e68e2dff18aea3576dc576b2e3ef1bbdd403cf42d69a7b47a30f6c755effe412"
        query = f"{flight} actual departure time"
        url = f"https://serpapi.com/search.json?q={query}&engine=google&api_key={api_key}"
        res = requests.get(url)
        data = res.json()
        snippets = [r.get("snippet", "") for r in data.get("organic_results", []) if "snippet" in r]
        return jsonify({"results": snippets[:3]})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/")
def home():
    return "Flight Tracker API running."

if __name__ == "__main__":
    app.run(debug=True, port=10000)
