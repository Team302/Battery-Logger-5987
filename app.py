from flask import Flask
from camera import scan_barcode
from battery import load_initial_battery_status, save_battery_status, auto_update_cooldown_statuses
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Load initial battery status and start background threads
load_initial_battery_status()

# Start the barcode scanning and cooldown threads
scanning_thread = threading.Thread(target=scan_barcode, daemon=True)
scanning_thread.start()

cooldown_thread = threading.Thread(target=auto_update_cooldown_statuses, daemon=True)
cooldown_thread.start()

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        save_battery_status()
