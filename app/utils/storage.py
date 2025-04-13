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

ASSIGNMENT_DATA_FILE = os.path.join("rubrics", "rubric_index.json")

def load_assignment_data():
    if not os.path.exists(ASSIGNMENT_DATA_FILE):
        return []
    with open(ASSIGNMENT_DATA_FILE, "r") as f:
        return json.load(f)

def save_assignment_data(data):
    with open(ASSIGNMENT_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

SUBMISSION_HISTORY_FILE = "all_submissions.json"

def store_submission_history(submission):
    if os.path.exists(SUBMISSION_HISTORY_FILE):
        with open(SUBMISSION_HISTORY_FILE, "r") as f:
            history = json.load(f)
    else:
        history = []

    history.append(submission)
    with open(SUBMISSION_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
