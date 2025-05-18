from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from datetime import datetime, timezone
import os

app = Flask(__name__, static_folder='static')
CORS(app)

FR24_BASE_URL = "https://api.flightradar24.com/common/v1/airport.json"
TOKEN = "88gO2cDKmNNThvUuglHVMyNgejftewp1N7hW-KeFtPQ"

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
    return int(datetime.now(timezone.utc).timestamp())

def format_time(timestamp):
    if not timestamp:
        return "--"
    try:
        dt = datetime.fromtimestamp(int(timestamp), timezone.utc)
        return dt.strftime("%H:%M")
    except:
        return "--"

def get_flight_status(real_time, scheduled_time):
    if not real_time or not scheduled_time:
        return "Scheduled"
    try:
        real_dt = datetime.fromtimestamp(int(real_time), timezone.utc)
        sched_dt = datetime.fromtimestamp(int(scheduled_time), timezone.utc)
        diff = (real_dt - sched_dt).total_seconds() / 60
        if diff < -5:
            return "Early"
        elif -5 <= diff <= 5:
            return "On Time"
        elif diff <= 30:
            return "Delayed"
        else:
            return "Delayed"
    except:
        return "Scheduled"

def fetch_flights(airport_code, mode):
    timestamp = get_current_timestamp()
    url = (f"{FR24_BASE_URL}?code={airport_code}&plugin[]=schedule&"
           f"plugin-setting[schedule][mode]={mode}&"
           f"plugin-setting[schedule][timestamp]={timestamp}&limit=100&page=1&token={TOKEN}")
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()
    flights = []

    if 'result' in data and 'response' in data['result'] and 'airport' in data['result']['response']:
        airport_data = data['result']['response']['airport']
        plugin_data = airport_data.get('pluginData', {}).get('schedule', {})
        if mode in plugin_data:
            flights_data = plugin_data[mode].get('data', [])
            for flight in flights_data:
                flight_info = flight.get('flight', {})
                identification = flight_info.get('identification', {})
                aircraft = flight_info.get('aircraft', {})
                airport = flight_info.get('airport', {})
                time = flight_info.get('time', {})
                
                if mode == 'arrivals':
                    flight_obj = {
                        'flightNumber': identification.get('number', {}).get('default', 'N/A'),
                        'from': airport.get('origin', {}).get('name', 'N/A'),
                        'eta': format_time(time.get('real', {}).get('arrival')),
                        'sta': format_time(time.get('scheduled', {}).get('arrival')),
                        'status': get_flight_status(time.get('real', {}).get('arrival'),
                                                    time.get('scheduled', {}).get('arrival')),
                        'registration': aircraft.get('registration', 'N/A'),
                        'callsign': identification.get('callsign', 'N/A'),
                        'airline': identification.get('operator', {}).get('name', 'N/A'),
                    }
                else:  # departures
                    flight_obj = {
                        'flightNumber': identification.get('number', {}).get('default', 'N/A'),
                        'to': airport.get('destination', {}).get('name', 'N/A'),
                        'etd': format_time(time.get('real', {}).get('departure')),
                        'std': format_time(time.get('scheduled', {}).get('departure')),
                        'status': get_flight_status(time.get('real', {}).get('departure'),
                                                    time.get('scheduled', {}).get('departure')),
                        'registration': aircraft.get('registration', 'N/A'),
                        'callsign': identification.get('callsign', 'N/A'),
                        'airline': identification.get('operator', {}).get('name', 'N/A'),
                    }
                flights.append(flight_obj)

    return flights

@app.route('/')
def serve_frontend():
    return send_from_directory('static', 'index.html')

@app.route('/api/flights/<station>/arrivals')
def arrivals_api(station):
    station = station.upper()
    try:
        arrivals = fetch_flights(station, 'arrivals')
        return jsonify({"success": True, "data": arrivals, "count": len(arrivals)})
    except requests.RequestException as e:
        return jsonify({"success": False, "error": f"Network error: {str(e)}", "data": []}), 503
    except Exception as e:
        return jsonify({"success": False, "error": f"Processing error: {str(e)}", "data": []}), 500

@app.route('/api/flights/<station>/departures')
def departures_api(station):
    station = station.upper()
    try:
        departures = fetch_flights(station, 'departures')
        return jsonify({"success": True, "data": departures, "count": len(departures)})
    except requests.RequestException as e:
        return jsonify({"success": False, "error": f"Network error: {str(e)}", "data": []}), 503
    except Exception as e:
        return jsonify({"success": False, "error": f"Processing error: {str(e)}", "data": []}), 500

@app.route('/api/flights/<station>/turnaround')
def turnaround_api(station):
    station = station.upper()
    try:
        arrivals = fetch_flights(station, 'arrivals')
        departures = fetch_flights(station, 'departures')

        arrival_by_reg = {f['registration']: f for f in arrivals if f['registration'] != 'N/A'}
        turnarounds = []

        for dep in departures:
            reg = dep['registration']
            if reg in arrival_by_reg:
                arr = arrival_by_reg[reg]
                turnaround = {
                    'flightNumber': f"{arr['flightNumber']} / {dep['flightNumber']}",
                    'from': arr['from'],
                    'to': dep['to'],
                    'arrival': arr['eta'],
                    'departure': dep['etd'],
                    'registration': reg,
                    'statusArrival': arr['status'],
                    'statusDeparture': dep['status'],
                }
                turnarounds.append(turnaround)

        return jsonify({"success": True, "data": turnarounds, "count": len(turnarounds)})
    except Exception as e:
        return jsonify({"success": False, "error": f"Processing error: {str(e)}", "data": []}), 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
