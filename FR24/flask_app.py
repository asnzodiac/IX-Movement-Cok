from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
import datetime
import os
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

# FlightRadar24 API Configuration
FR24_BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
AIRPORT_CODE = "COK"
TOKEN = "88gO2cDKmNNThvUuglHVMyNgejftewp1N7hW-KeFtPQ"

# Headers to mimic browser requests
HEADERS = {
    "accept": "*/*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "referer": "https://www.flightradar24.com/"
}

def get_current_timestamp():
    """Get current timestamp for API requests"""
    return int(datetime.now(timezone.utc).timestamp())

def format_time(timestamp):
    """Convert timestamp to readable time format"""
    if not timestamp:
        return "--"
    try:
        dt = datetime.fromtimestamp(int(timestamp), timezone.utc)
        return dt.strftime("%H:%M")
    except:
        return "--"

def get_flight_status(real_time, scheduled_time):
    """Determine flight status based on times"""
    if not real_time or not scheduled_time:
        return "Scheduled"
    
    try:
        real_dt = datetime.fromtimestamp(int(real_time), timezone.utc)
        sched_dt = datetime.fromtimestamp(int(scheduled_time), timezone.utc)
        diff = (real_dt - sched_dt).total_seconds() / 60
        
        if diff <= -5:
            return "Early"
        elif diff <= 5:
            return "On Time"
        elif diff <= 30:
            return "Delayed"
        else:
            return "Delayed"
    except:
        return "Scheduled"

@app.route('/')
def index():
    """Serve the frontend HTML"""
    with open('index.html', 'r') as f:
        return f.read()

@app.route('/api/flights/cok/arrivals')
def get_arrivals():
    """Fetch arrivals data from FlightRadar24"""
    try:
        timestamp = get_current_timestamp()
        url = f"{FR24_BASE_URL}?code={AIRPORT_CODE}&plugin[]=schedule&plugin-setting[schedule][mode]=arrivals&plugin-setting[schedule][timestamp]={timestamp}&limit=100&page=1&token={TOKEN}"
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        arrivals = []
        if 'result' in data and 'response' in data['result'] and 'airport' in data['result']['response']:
            airport_data = data['result']['response']['airport']
            if 'pluginData' in airport_data and 'schedule' in airport_data['pluginData']:
                arrivals_data = airport_data['pluginData']['schedule']['arrivals']['data']
                
                for flight in arrivals_data:
                    flight_info = flight['flight']
                    identification = flight_info.get('identification', {})
                    aircraft = flight_info.get('aircraft', {})
                    airport = flight_info.get('airport', {})
                    time = flight_info.get('time', {})
                    status = flight_info.get('status', {})
                    
                    arrival = {
                        'flightNumber': identification.get('number', {}).get('default', 'N/A'),
                        'from': airport.get('origin', {}).get('name', 'N/A'),
                        'eta': format_time(time.get('real', {}).get('arrival')),
                        'sta': format_time(time.get('scheduled', {}).get('arrival')),
                        'status': get_flight_status(
                            time.get('real', {}).get('arrival'),
                            time.get('scheduled', {}).get('arrival')
                        ),
                        'registration': aircraft.get('registration', 'N/A'),
                        'airline': identification.get('row', 0),
                        'callsign': identification.get('callsign', 'N/A')
                    }
                    arrivals.append(arrival)
        
        return jsonify({"success": True, "data": arrivals, "count": len(arrivals)})
    
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Network error: {str(e)}", "data": []}), 503
    except Exception as e:
        return jsonify({"success": False, "error": f"Processing error: {str(e)}", "data": []}), 500

@app.route('/api/flights/cok/departures')
def get_departures():
    """Fetch departures data from FlightRadar24"""
    try:
        timestamp = get_current_timestamp()
        url = f"{FR24_BASE_URL}?code={AIRPORT_CODE}&plugin[]=schedule&plugin-setting[schedule][mode]=departures&plugin-setting[schedule][timestamp]={timestamp}&limit=100&page=1&token={TOKEN}"
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        departures = []
        if 'result' in data and 'response' in data['result'] and 'airport' in data['result']['response']:
            airport_data = data['result']['response']['airport']
            if 'pluginData' in airport_data and 'schedule' in airport_data['pluginData']:
                departures_data = airport_data['pluginData']['schedule']['departures']['data']
                
                for flight in departures_data:
                    flight_info = flight['flight']
                    identification = flight_info.get('identification', {})
                    aircraft = flight_info.get('aircraft', {})
                    airport = flight_info.get('airport', {})
                    time = flight_info.get('time', {})
                    status = flight_info.get('status', {})
                    
                    departure = {
                        'flightNumber': identification.get('number', {}).get('default', 'N/A'),
                        'to': airport.get('destination', {}).get('name', 'N/A'),
                        'etd': format_time(time.get('real', {}).get('departure')),
                        'std': format_time(time.get('scheduled', {}).get('departure')),
                        'status': get_flight_status(
                            time.get('real', {}).get('departure'),
                            time.get('scheduled', {}).get('departure')
                        ),
                        'registration': aircraft.get('registration', 'N/A'),
                        'airline': identification.get('row', 0),
                        'callsign': identification.get('callsign', 'N/A')
                    }
                    departures.append(departure)
        
        return jsonify({"success": True, "data": departures, "count": len(departures)})
    
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Network error: {str(e)}", "data": []}), 503
    except Exception as e:
        return jsonify({"success": False, "error": f"Processing error: {str(e)}", "data": []}), 500

@app.route('/api/flights/cok/turnaround')
def get_turnaround():
    """Fetch turnaround flights (flights that both arrive and depart)"""
    try:
        # Get both arrivals and departures
        arrivals_response = get_arrivals()
        departures_response = get_departures()
        
        arrivals_data = arrivals_response.get_json()
        departures_data = departures_response.get_json()
        
        if not arrivals_data['success'] or not departures_data['success']:
            return jsonify({"success": False, "error": "Failed to fetch flight data", "data": []})
        
        arrivals = arrivals_data['data']
        departures = departures_data['data']
        
        # Match flights by registration number to find turnarounds
        turnarounds = []
        arrival_by_reg = {flight['registration']: flight for flight in arrivals if flight['registration'] != 'N/A'}
        
        for departure in departures:
            if departure['registration'] in arrival_by_reg:
                arrival = arrival_by_reg[departure['registration']]
                turnaround = {
                    'flightNumber': f"{arrival['flightNumber']} / {departure['flightNumber']}",
                    'from': arrival['from'],
                    'to': departure['to'],
                    'arrival': arrival['eta'],
                    'departure': departure['etd'],
                    'registration': departure['registration']
                }
                turnarounds.append(turnaround)
        
        return jsonify({"success": True, "data": turnarounds, "count": len(turnarounds)})
    
    except Exception as e:
        return jsonify({"success": False, "error": f"Processing error: {str(e)}", "data": []}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})

if __name__ == '__main__':
    # Get port from environment variable (required for Render deployment)
    port = int(os.environ.get('PORT', 5000))
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)
