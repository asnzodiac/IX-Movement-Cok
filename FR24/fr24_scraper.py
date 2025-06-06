from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

FR24_URL = "https://data-live.flightradar24.com/zones/fcgi/feed.js"

@app.route("/")
def home():
    return "✅ Flight Tracker backend is running!"

@app.route("/flights")
def get_flights():
    try:
        airport = request.args.get("airport", "COK")
        mode = request.args.get("type", "arrivals")
        res = requests.get(FR24_URL, params={
            "airport": airport,
            mode: 1
        }, headers={"User-Agent": "Mozilla/5.0"})
        data = res.json()
        flights = []
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            flight_no = v.get("flight", "")
            if not flight_no:
                continue
            # Prefix filter disabled for testing:
            # if not flight_no.startswith(ALLOWED_PREFIXES):
            #     continue
            flights.append({
                "flight": flight_no,
                "reg": v.get("reg", ""),
                "from": v.get("origin", ""),
                "to": v.get("destination", ""),
                "eta": v.get("eta", v.get("lastSeen", "")),
                "status": v.get("status", "")
            })
        return jsonify(flights)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
