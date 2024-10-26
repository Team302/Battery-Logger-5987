import threading

# Constants and settings
PERSISTENT_FILE = 'battery_status.json'
COOLDOWN_DURATION_TIME = 600  # in seconds
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480

# Lock for thread safety
battery_status_lock = threading.Lock()

# Initialize battery status dictionary
battery_status = {}
