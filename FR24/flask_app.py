import requests
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/flights/cok/arrivals')
def get_arrivals():
    # Use the FlightRadar24 API URL you provided
    url = "https://api.flightradar24.com/common/v1/airport.json?code=COK&plugin[]=schedule&plugin-setting[schedule][mode]=arrivals&plugin-setting[schedule][timestamp]=1747585538&limit=100&page=1&token=YOUR_TOKEN"
    
    response = requests.get(url)
    data = response.json()
    
    # Parse and format the data according to your needs
    formatted_data = parse_arrivals_data(data)
    
    return jsonify({"success": True, "data": formatted_data})
