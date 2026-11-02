import os
import random
import sqlite3
from datetime import datetime, timedelta

def seed_demo_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'data', 'deskmate.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear old data for clean seed
    cursor.execute("DELETE FROM activity_log")
    cursor.execute("DELETE FROM energy_log")
    cursor.execute("DELETE FROM nudge_log")
    cursor.execute("DELETE FROM nudge_decision_log")

    now = datetime.now()
    start_time = (now - timedelta(days=5)).replace(minute=0, second=0, microsecond=0)

    apps = [('Visual Studio Code', 'code.exe'), ('Google Chrome', 'chrome.exe'), ('Slack', 'slack.exe'), ('Terminal', 'window.exe'), ('Zoom Meeting', 'zoom.exe')]

    act_rows = []
    en_rows = []
    nudge_rows = []
    dec_rows = []

    current_time = start_time
    while current_time <= now:
        h = current_time.hour
        m = current_time.minute
        is_work_hour = 8 <= h <= 19

        if is_work_hour:
            # Morning peak
            if 8 <= h <= 11:
                keys = random.randint(110, 190)
                mouse = random.randint(20, 45)
                idle = random.uniform(0, 15)
                in_flow = 1 if keys >= 120 else 0
            elif 12 <= h <= 13:
                keys = random.randint(20, 60)
                mouse = random.randint(10, 25)
                idle = random.uniform(30, 90)
                in_flow = 0
            elif 14 <= h <= 16:
                keys = random.randint(60, 110)
                mouse = random.randint(15, 30)
                idle = random.uniform(10, 35)
                in_flow = 0
            else:
                keys = random.randint(80, 150)
                mouse = random.randint(15, 35)
                idle = random.uniform(5, 25)
                in_flow = 1 if keys >= 120 else 0

            app_title, app_proc = random.choice(apps)
            t_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

            act_rows.append((t_str, keys, mouse, app_title, app_proc, idle))

            # Periodic nudge decision
            if m in (0, 20, 40):
                dec = 'delayed' if in_flow else 'fired'
                reason = 'in_flow_delayed' if in_flow else 'fired'
                dec_rows.append((t_str, 'water_reminder', dec, reason, keys, mouse, idle, float(random.randint(10, 80)), float(random.randint(5, 45)), in_flow, None))

            # Energy check-ins 4 times a day
            if m == 0 and h in (9, 12, 15, 18):
                if h == 9:
                    energy = random.choice([4, 5])
                    note = 'Morning high energy'
                elif h == 12:
                    energy = random.choice([3, 4])
                    note = 'Pre-lunch status'
                elif h == 15:
                    energy = random.choice([1, 2, 3])
                    note = 'Afternoon fatigue dip'
                else:
                    energy = random.choice([2, 3, 4])
                    note = 'End of workday review'

                en_rows.append((t_str, energy, 'periodic_checkin', note))
                nudge_rows.append((t_str, 'energy_checkin', f'Check-in: {energy}/5', 'acted'))

        current_time += timedelta(minutes=5)

    cursor.executemany("INSERT INTO activity_log (timestamp, keys_per_min, mouse_events_per_min, active_window_title, active_process_name, idle_seconds) VALUES (?, ?, ?, ?, ?, ?)", act_rows)
    cursor.executemany("INSERT INTO energy_log (timestamp, energy_level, prompt_type, notes) VALUES (?, ?, ?, ?)", en_rows)
    cursor.executemany("INSERT INTO nudge_log (timestamp, nudge_type, message, action) VALUES (?, ?, ?, ?)", nudge_rows)
    cursor.executemany("INSERT INTO nudge_decision_log (timestamp, nudge_type, decision, reason, keys_per_min, mouse_events_per_min, idle_seconds, continuous_active_min, continuous_typing_min, is_in_flow, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", dec_rows)

    conn.commit()
    conn.close()
    print(f"Successfully seeded {len(act_rows)} activity logs, {len(en_rows)} energy ratings, {len(dec_rows)} decisions.")

if __name__ == '__main__':
    seed_demo_data()
