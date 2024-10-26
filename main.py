import os

import cv2
import time
import csv
import threading
from pyzbar.pyzbar import decode
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, Response
import json
import os
import pygame
pygame.mixer.init()

# Define the path for persistent data storage
PERSISTENT_FILE = 'battery_status.json'

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure random key

# Create a lock for thread safety
battery_status_lock = threading.Lock()

COOLDOWN_DURATION_TIME = 10 #minutes
# Battery status tracking dictionary
battery_status = {}

cap = cv2.VideoCapture(0)  # Open the default camera

# Initialize the CSV file and write headers if it doesn’t exist
def initialize_csv():
    with open('battery_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:  # Check if file is empty
            writer.writerow([
                "Timestamp",
                "Battery Code",
                "Team Number",
                "Purchase Year",
                "Purchase Month",
                "Battery Number",
                "Status"
            ])


# Parse battery code
def parse_battery_code(barcode_data):
    team_number = barcode_data[:4]
    purchase_year = barcode_data[4:8]
    purchase_month = barcode_data[8:10]
    battery_number = barcode_data[10:12]

    return {
        "team_number": team_number,
        "purchase_year": purchase_year,
        "purchase_month": purchase_month,
        "battery_number": battery_number
    }


# Log scan data to CSV
def log_to_csv(barcode_data, battery_info, status):
    initialize_csv()  # Ensure CSV is initialized
    with open('battery_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([
            timestamp,
            barcode_data,
            battery_info['team_number'],
            battery_info['purchase_year'],
            battery_info['purchase_month'],
            battery_info['battery_number'],
            status
        ])


# Update battery status with timestamp
def update_battery_status(barcode_data, new_status):
    battery_status[barcode_data] = {
        'status': new_status,
        'last_change': datetime.now()
    }
    print(
        f"[update_battery_status] Battery {barcode_data} status updated to {new_status} at {battery_status[barcode_data]['last_change']}")


# Check if battery can change status based on 10-minute wait rule
def can_change_status(barcode_data, new_status):
    with battery_status_lock:
        if barcode_data in battery_status:
            last_status = battery_status[barcode_data]['status']
            last_change = battery_status[barcode_data]['last_change']

            # Check 10-minute wait from last status change
            if datetime.now() - last_change < timedelta(seconds=10):
                return False

            # Logic to enforce allowed transitions
            valid_transitions = {
                "Charging": ["Cooldown To Robot"],
                "Cooldown To Robot": ["Ready for ROBOT"],
                "Ready for ROBOT": ["In Use"],
                "In Use": ["Cooldown To Charge"],
                "Cooldown To Charge": ["Ready for CHARGING"],
                "Ready for CHARGING": ["Charging"]
            }

            if new_status in valid_transitions.get(last_status, []):
                return True
        else:
            # Allow initialization to "Charging"
            if new_status == "Charging":
                return True
    return False




# Barcode scanning function
def scan_barcode():
    print("Starting barcode scanning...")
    scanned_barcodes = {}
    cooldown_time = 5

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture image")
            break

        barcodes = decode(frame)

        for barcode in barcodes:
            barcode_data = barcode.data.decode('utf-8')[:-1]  # Discard last digit
            battery_info = parse_battery_code(barcode_data)

            if battery_info['team_number'] != "5987":
                continue

            if barcode_data not in scanned_barcodes or time.time() - scanned_barcodes[barcode_data] > cooldown_time:
                scanned_barcodes[barcode_data] = time.time()
                print(f"Scanned Barcode: {barcode_data}")

                with battery_status_lock:
                    current_status = battery_status.get(barcode_data, {}).get('status', 'Charging')

                # Determine the next status based on current status and wait rules
                if can_change_status(barcode_data, "Cooldown To Robot"):
                    new_status = "Cooldown To Robot"
                elif can_change_status(barcode_data, "Ready for ROBOT"):
                    new_status = "Ready for ROBOT"
                elif can_change_status(barcode_data, "In Use"):
                    new_status = "In Use"
                elif can_change_status(barcode_data, "Cooldown To Charge"):
                    new_status = "Cooldown To Charge"
                elif can_change_status(barcode_data, "Ready for CHARGING"):
                    new_status = "Ready for CHARGING"
                elif can_change_status(barcode_data, "Charging"):
                    new_status = "Charging"
                else:
                    print(f"Battery {barcode_data} cannot change status yet.")
                    continue

                log_to_csv(barcode_data, battery_info, new_status)
                update_battery_status(barcode_data, new_status)

                pygame.mixer.music.load("beep.wav")  # Replace 'beep.wav' with your actual sound file path
                pygame.mixer.music.play()


        time.sleep(0.1)  # Small delay to reduce CPU usage

    cap.release()


# Background thread to auto-update cooldown statuses
def auto_update_cooldown_statuses():
    COOLDOWN_DURATION = timedelta(seconds=COOLDOWN_DURATION_TIME)
    print("Starting cooldown status updater...")
    while True:
        try:
            print(f"[{datetime.now()}] Auto-update thread is running.")
            with battery_status_lock:
                for barcode_data, data in list(battery_status.items()):
                    status = data['status']
                    last_change = data['last_change']
                    elapsed_time = datetime.now() - last_change
                    print(
                        f"[auto_update_cooldown_statuses] Battery {barcode_data}: Status = {status}, Elapsed Time = {elapsed_time}, Cooldown Duration = {COOLDOWN_DURATION}")

                    # Check for "Cooldown To Robot" with refined condition
                    if status == "Cooldown To Robot" and elapsed_time >= COOLDOWN_DURATION:
                        new_status = "Ready for ROBOT"
                        battery_info = parse_battery_code(barcode_data)
                        log_to_csv(barcode_data, battery_info, new_status)
                        update_battery_status(barcode_data, new_status)
                        print(
                            f"[auto_update_cooldown_statuses] Battery {barcode_data} automatically updated to {new_status}")

                    # Check for "Cooldown To Charge"
                    elif status == "Cooldown To Charge" and elapsed_time >= COOLDOWN_DURATION:
                        new_status = "Ready for CHARGING"
                        battery_info = parse_battery_code(barcode_data)
                        log_to_csv(barcode_data, battery_info, new_status)
                        update_battery_status(barcode_data, new_status)
                        print(
                            f"[auto_update_cooldown_statuses] Battery {barcode_data} automatically updated to {new_status}")
        except Exception as e:
            print(f"Exception in auto_update_cooldown_statuses: {e}")
        time.sleep(5)


# Flask route to display battery statuses
@app.route('/')
def index():
    with battery_status_lock:
        battery_info = [
            {
                'battery_code': code,
                'status': data['status'],
                'last_change': data['last_change'].strftime("%Y-%m-%d %H:%M:%S")
            } for code, data in battery_status.items()
        ]
    return render_template('index.html', batteries=battery_info)


# Flask route for manual battery code entry
@app.route('/manual_entry', methods=['POST'])
def manual_entry():
    battery_code = request.form.get('battery_code')

    if not battery_code:
        flash('Please enter a battery code.', 'error')
        return redirect(url_for('index'))

    battery_code = battery_code.strip()
    battery_code = battery_code

    battery_info = parse_battery_code(battery_code)

    if battery_info['team_number'] != "5987":
        flash('Invalid team number in battery code.', 'error')
        return redirect(url_for('index'))

    with battery_status_lock:
        current_status = battery_status.get(battery_code, {}).get('status', 'Charging')

    # Determine the next status based on current status and wait rules
    if can_change_status(battery_code, "Cooldown To Robot"):
        new_status = "Cooldown To Robot"
    elif can_change_status(battery_code, "Ready for ROBOT"):
        new_status = "Ready for ROBOT"
    elif can_change_status(battery_code, "In Use"):
        new_status = "In Use"
    elif can_change_status(battery_code, "Cooldown To Charge"):
        new_status = "Cooldown To Charge"
    elif can_change_status(battery_code, "Ready for CHARGING"):
        new_status = "Ready for CHARGING"
    elif can_change_status(battery_code, "Charging"):
        new_status = "Charging"
    else:
        flash(f"Battery {battery_code} cannot change status yet.", 'error')
        return redirect(url_for('index'))

    log_to_csv(battery_code, battery_info, new_status)
    update_battery_status(battery_code, new_status)

    flash(f"Battery {battery_code} status updated to {new_status}.", 'success')
    return redirect(url_for('index'))


# API endpoint to provide battery status as JSON
@app.route('/api/battery_status')
def battery_status_api():
    with battery_status_lock:
        battery_info = [
            {
                'battery_code': code,
                'status': data['status'],
                'last_change': data['last_change'].strftime("%Y-%m-%d %H:%M:%S")
            } for code, data in battery_status.items()
        ]
    return jsonify(battery_info)

@app.route('/logs')
def logs():
    logs = []
    # Read the CSV file
    try:
        with open('battery_log.csv', mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                logs.append(row)
    except FileNotFoundError:
        flash("Log file not found.", "error")

    # Pass logs data to the template
    return render_template('logs.html', logs=logs)
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_frames():
    while True:
        success, frame = cap.read()  # Capture frame-by-frame
        if not success:
            break
        else:
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Use yield to create a generator and stream the video
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
def save_battery_status():
    with open(PERSISTENT_FILE, 'w') as f:
        # Convert datetimes to strings for JSON compatibility
        data_to_save = {
            code: {
                'status': data['status'],
                'last_change': data['last_change'].strftime("%Y-%m-%d %H:%M:%S")
            }
            for code, data in battery_status.items()
        }
        json.dump(data_to_save, f)
    print("Battery status saved to file.")


def load_initial_battery_status():
    if os.path.exists(PERSISTENT_FILE):
        with open(PERSISTENT_FILE, 'r') as f:
            data_loaded = json.load(f)
            print("DATA: ", data_loaded)
            for code, data in data_loaded.items():
                battery_status[code] = {
                    'status': data['st'
                                   'atus'],
                    'last_change': datetime.strptime(data['last_change'], "%Y-%m-%d %H:%M:%S")
                }
        print("Battery status loaded from file.")
    else:
        print("No persistent file found; starting with an empty battery status.")


# Start the Flask app and background tasks
if __name__ == "__main__":
    # Load initial battery status from persistent file
    load_initial_battery_status()

    # Initialize CSV if necessary
    initialize_csv()

    # Start the barcode scanning in a background thread
    scanning_thread = threading.Thread(target=scan_barcode, daemon=True)
    scanning_thread.start()

    # Start the auto-update cooldown statuses in a background thread
    cooldown_thread = threading.Thread(target=auto_update_cooldown_statuses, daemon=True)
    cooldown_thread.start()

    try:
        app.run(host='0.0.0.0', port=5000,debug=True, use_reloader=False)
    finally:
        # Save battery status to persistent file on exit
        save_battery_status()
