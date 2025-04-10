import os
import json

PENDING_DIR = os.path.join("pending_feedback")

def store_pending_feedback(submission_id, data):
    if not os.path.exists(PENDING_DIR):
        os.makedirs(PENDING_DIR)
    filepath = os.path.join(PENDING_DIR, f"{submission_id}.json")
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def load_pending_feedback(submission_id):
    filepath = os.path.join(PENDING_DIR, f"{submission_id}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)

def load_all_pending_feedback():
    if not os.path.exists(PENDING_DIR):
        return []
    all_data = []
    for fname in os.listdir(PENDING_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(PENDING_DIR, fname), "r") as f:
                all_data.append(json.load(f))
    return all_data
