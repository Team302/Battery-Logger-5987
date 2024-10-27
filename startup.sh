#!/bin/bash

# Navigate to the project directory
cd /home/david/Documents/Battery-Logger-5987

# Activate the virtual environment
source battery_project_env/bin/activate

echo "Starting Battery Manager..."

# Logging start time
echo "Battery Manager started at $(date)" >> /home/david/Documents/Battery-Logger-5987/usingLogger.log

# Start the main Python script
python3 main.py &

# Check network connectivity to localhost
echo "Checking network connectivity..."
ping -c 4 127.0.0.1

# Open the local URL in the browser
echo "Opening 127.0.0.1:5000 in the browser..."
xdg-open http://127.0.0.1:5000

# Example loop to simulate periodic checks
while true; do
    echo "Checking battery statuses..."
    # Add any functions or checks here
    sleep 300
done
