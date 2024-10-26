from flask import render_template, redirect, request, flash, url_for
from app import app
from config import battery_status, battery_status_lock
from battery import parse_battery_code, can_change_status, update_battery_status
from utils import log_to_csv


# Flask route to display battery statuses
@app.route('/')
def index():
    with battery_status_lock:
        battery_info = [
            {
                'battery_code': code,
                'status': data['status'],
                'display_time': data.get('display_time', '00:00:00')  # Display formatted time (either elapsed or remaining)
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
