#!/bin/bash

# Example startup script for FRC battery management
echo "Starting Battery Manager..."

# Logging start time
echo "Battery Manager started at $(date)" >> /home/david/Documents/Battery-Logger-5987/usingLogger.log

python3 /home/david/Documents/Battery-Logger-5987/main.py &

echo "Checking network connectivity..."
ping -c 4 http://127.0.0.1:5000

echo "Opening 127.0.0.1:5000 in the browser..."
xdg-open http://127.0.0.1:5000

# Example loop to simulate periodic checks
while true; do
    echo "Checking battery statuses..."
    # Call scan_battery or other functions to manage batteries
    scan_battery

    # Wait for 5 minutes before the next check (adjust as needed)
    sleep 300
done
