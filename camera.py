import time
import pygame
import cv2
from pyzbar.pyzbar import decode
from config import battery_status, battery_status_lock
from battery import parse_battery_code, update_battery_status, can_change_status
from utils import log_to_csv

pygame.mixer.init()
cap = cv2.VideoCapture(0)

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
            barcode_data = barcode.data.decode('utf-8')[:-1]
            battery_info = parse_battery_code(barcode_data)

            if battery_info['team_number'] != "5987":
                continue

            if barcode_data not in scanned_barcodes or time.time() - scanned_barcodes[barcode_data] > cooldown_time:
                scanned_barcodes[barcode_data] = time.time()
                print(f"Scanned Barcode: {barcode_data}")

                with battery_status_lock:
                    current_status = battery_status.get(barcode_data, {}).get('status', 'Charging')

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

                pygame.mixer.music.load("static/beep.wav")  # Ensure beep.wav is in the static folder
                pygame.mixer.music.play()

        time.sleep(0.1)  # Small delay to reduce CPU usage

    cap.release()
