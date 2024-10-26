import json
import os
import csv
import time
from datetime import datetime, timedelta
from config import battery_status, battery_status_lock, COOLDOWN_DURATION_TIME, PERSISTENT_FILE


# Initialize the CSV file
def initialize_csv():
    with open('battery_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(
                ["Timestamp", "Battery Code", "Team Number", "Purchase Year", "Purchase Month", "Battery Number",
                 "Status"])


# Parse barcode data into individual components
def parse_battery_code(barcode_data):
    team_number = barcode_data[:4]
    purchase_year = barcode_data[4:8]
    purchase_month = barcode_data[8:10]
    battery_number = barcode_data[10:12]
    return {"team_number": team_number, "purchase_year": purchase_year, "purchase_month": purchase_month,
            "battery_number": battery_number}


# Load battery status from JSON file
def load_initial_battery_status():
    if os.path.exists(PERSISTENT_FILE):
        with open(PERSISTENT_FILE, 'r') as f:
            data_loaded = json.load(f)
            for code, data in data_loaded.items():
                battery_status[code] = {
                    'status': data['status'],
                    'display_time': timedelta(0),
                    'last_change': datetime.strptime(data['last_change'], "%Y-%m-%d %H:%M:%S")
                }
        print("Battery status loaded from file.")
    else:
        print("No persistent file found; starting with an empty battery status.")


# Save battery status to JSON file
def save_battery_status():
    with open(PERSISTENT_FILE, 'w') as f:
        data_to_save = {
            code: {
                'status': data['status'],
                'last_change': data['last_change'].strftime("%Y-%m-%d %H:%M:%S")
            }
            for code, data in battery_status.items()
        }
        json.dump(data_to_save, f)


# Checks if the battery status can be changed to the desired status
def can_change_status(barcode_data, new_status):
    with battery_status_lock:
        if barcode_data in battery_status:
            last_status = battery_status[barcode_data]['status']
            last_change = battery_status[barcode_data]['last_change']

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
        elif new_status == "Charging":
            return True
    return False


def update_battery_status(barcode_data, new_status):
    with battery_status_lock:
        battery_status[barcode_data] = {
            'status': new_status,
            'display_time': timedelta(0),
            'last_change': datetime.now()
        }
    print(
        f"[update_battery_status] Battery {barcode_data} status updated to {new_status} at {battery_status[barcode_data]['last_change']}")


# Background thread to automatically update cooldown statuses
def auto_update_cooldown_statuses():
    while True:
        with battery_status_lock:
            for barcode_data, data in battery_status.items():
                status = data['status']
                last_change = data['last_change']
                current_time = datetime.now()

                if status in ["Cooldown To Robot", "Cooldown To Charge"]:
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
