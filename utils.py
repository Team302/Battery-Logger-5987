import csv
from datetime import datetime

def log_to_csv(barcode_data, battery_info, status):
    with open('battery_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([
            timestamp, barcode_data, battery_info['team_number'],
            battery_info['purchase_year'], battery_info['purchase_month'],
            battery_info['battery_number'], status
        ])
