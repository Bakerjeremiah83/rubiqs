import os
import json
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "activity_log.json")

def log_activity(action, user="system", details=""):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user": user,
        "action": action,
        "details": details
    }

    # Ensure logs directory exists
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    # Load or create log file
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w") as f:
            json.dump([], f)

    with open(LOG_PATH, "r") as f:
        logs = json.load(f)

    logs.insert(0, entry)

    with open(LOG_PATH, "w") as f:
        json.dump(logs, f, indent=2)
