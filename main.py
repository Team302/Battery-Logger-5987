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
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
# Define the path for persistent data storage
PERSISTENT_FILE = 'battery_status.json'
stop_flag = threading.Event()  # Create an Event object to signal threads to stop

app = Flask(__name__)
app.secret_key = '1234567890'

# Define team number default
TEAM_NUMBER = "5987"
# Create a lock for thread safety
battery_status_lock = threading.Lock()

COOLDOWN_DURATION_TIME = 600  # seconds

# Battery status tracking dictionary
battery_status = {}


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
                "Battery Number",
                "Status"
            ])


# Parse battery code
def parse_battery_code(barcode_data):
    team_number = barcode_data[:4]
    purchase_year = barcode_data[4:8]
    battery_number = barcode_data[8:12]

    return {
        "team_number": team_number,
        "purchase_year": purchase_year,
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
            battery_info['battery_number'],
            status
        ])


# Update battery status with timestamp
def update_battery_status(barcode_data, new_status):
    battery_status[barcode_data] = {
        'status': new_status,
        'display_time': timedelta(0),
        'last_change': datetime.now()
    }
    print(
        f"[update_battery_status] Battery {barcode_data} status updated to {new_status} at {battery_status[barcode_data]['last_change']}")


def can_change_status(barcode_data, new_status):
    with battery_status_lock:
        if barcode_data in battery_status:
            last_status = battery_status[barcode_data]['status']
            last_change = battery_status[barcode_data]['last_change']

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
    cooldown_time = 2

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture image")
            break

        barcodes = decode(frame)

        for barcode in barcodes:
            barcode_data = barcode.data.decode('utf-8')[:-1]  # Discard last digit
            battery_info = parse_battery_code(barcode_data)
            if not (barcode_data in battery_status.keys()):
                break

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
    while True:
        with battery_status_lock:
            for barcode_data, data in battery_status.items():
                status = data['status']
                last_change = data['last_change']
                current_time = datetime.now()

                if status in ["Cooldown To Robot", "Cooldown To Charge"]:
                    # Calculate remaining cooldown time as a countdown timer
                    elapsed_time = current_time - last_change
                    display_time = max(timedelta(seconds=COOLDOWN_DURATION_TIME) - elapsed_time, timedelta(0))
                    hours = int(display_time.total_seconds() // 3600)
                    minutes = int((display_time.total_seconds() % 3600) // 60)
                    seconds = int(display_time.total_seconds() % 60)

                    battery_status[barcode_data]['display_time'] = f"{hours}:{minutes:02}:{seconds:02}"

                    # If countdown reaches zero, change status to ready
                    if display_time == timedelta(0):
                        new_status = "Ready for ROBOT" if status == "Cooldown To Robot" else "Ready for CHARGING"
                        update_battery_status(barcode_data, new_status)

                else:
                    # Show elapsed time as a timer going up
                    elapsed_time = current_time - last_change
                    hours = int(elapsed_time.total_seconds() // 3600)
                    minutes = int((elapsed_time.total_seconds() % 3600) // 60)
                    seconds = int(elapsed_time.total_seconds() % 60)

                    battery_status[barcode_data]['display_time'] = f"{hours}:{minutes:02}:{seconds:02}"

        time.sleep(1)  # Check every second for countdown accuracy


# Flask route to display battery statuses
@app.route('/')
def index():
    with battery_status_lock:
        battery_info = [
            {
                'battery_code': code,
                'status': data['status'],
                'display_time': data.get('display_time', '00:00:00')
                # Display formatted time (either elapsed or remaining)
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

    if not (battery_code in battery_status.keys()):
        flash('Invalid team number in battery code. Please check Settings', 'error')
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
                'display_time': str(data['display_time']),
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
        success, frame = cap.read()
        if not success:
            break
        else:
            # Encode the frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Yield the frame as part of the response
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global COOLDOWN_DURATION_TIME
    global TEAM_NUMBER
    if request.method == 'POST':
        # Retrieve and apply settings
        try:
            COOLDOWN_DURATION_TIME = int(request.form.get('cooldown_time', COOLDOWN_DURATION_TIME))
            TEAM_NUMBER = int(request.form.get('team_number', TEAM_NUMBER))
            flash("Settings have been updated.", "success")
        except:
            try:
                TEAM_NUMBER = int(request.form.get('team_number', TEAM_NUMBER))
                flash("Settings have been updated (ONLY TEAM NUMBER)", "success")
            except:
                try:
                    COOLDOWN_DURATION_TIME = int(request.form.get('cooldown_time', COOLDOWN_DURATION_TIME))
                    flash("Settings have been updated (ONLY COOLDOWN)", "success")
                except:
                    flash("Settings have NOT been updated.", "warning")

    return render_template('settings.html')


@app.route('/add_battery', methods=['POST'])
def add_battery():
    global TEAM_NUMBER

    # Get current year
    current_year = datetime.now().year

    # Initialize battery number as a string with leading zeros
    number = 1
    battery_number = f"{number:04d}"  # Format number as "0001"
    battery_code = f"{TEAM_NUMBER}{current_year}{battery_number}"

    # Increment battery number if code already exists
    while battery_code in battery_status:
        number += 1
        battery_number = f"{number:04d}"  # Format number with leading zeros
        battery_code = f"{TEAM_NUMBER}{current_year}{battery_number}"

    # Add the new battery to `battery_status`
    battery_status[battery_code] = {
        'status': 'Charging',
        'last_change': datetime.now(),
        'display_time': timedelta(0),
    }

    # Return a JSON response
    return jsonify({'message': f"Battery {battery_code} added successfully."})



@app.route('/stop', methods=['POST'])
def stop_system():
    stop_flag.set()  # Set the stop flag to terminate background threads
    flash("System stopped successfully. Shutting down...", "success")

    # Give a moment for flash message to register
    time.sleep(1)

    # Exit the program
    save_battery_status()
    os.abort()  # Forcefully terminate the Flask server and Python process
    # Alternatively, use sys.exit() but note that os._exit(0) ensures immediate termination


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
                    'status': data['status'],
                    'display_time': timedelta(0),
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
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        # Save battery status to persistent file on exit
        save_battery_status()
