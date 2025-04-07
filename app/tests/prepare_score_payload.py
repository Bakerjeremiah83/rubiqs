import os
import json
from datetime import datetime

# Simulated decoded launch data (as you'd get from the LTI launch)
launch_data = {
    "sub": "2",
    "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
        "lineitem": "http://localhost:8080/mod/lti/services.php/3/lineitems/8/lineitem?type_id=3",
        "scope": [
            "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
            "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly",
            "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly",
            "https://purl.imsglobal.org/spec/lti-ags/scope/score"
        ]
    }
}

# Simulated GPT-generated score (already rubric-based)
score = 37  # ← should be generated from the rubric + submission evaluation

# Path to rubric file (this should be passed alongside the submission in actual use)
rubric_path = "rubrics/current_submission_rubric.json"

# Load rubric to extract total points
try:
    with open(rubric_path, "r") as f:
        rubric = json.load(f)
        total_points = rubric.get("total_points")

        # Fallback: calculate from criteria if total_points isn't directly provided
        if total_points is None and "criteria" in rubric:
            total_points = sum(c.get("points", 0) for c in rubric["criteria"])

except Exception as e:
    print(f"[Rubiqs Warning] Failed to load rubric or calculate total_points: {e}")
    total_points = None  # Leave blank if not found

# Prepare the AGS score submission
lineitem_url = launch_data["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"]["lineitem"]
score_url = lineitem_url.split("?")[0] + "/scores"

score_payload = {
    "userId": launch_data["sub"],
    "scoreGiven": score,
    "scoreMaximum": total_points,  # ✅ now based on rubric
    "activityProgress": "Completed",
    "gradingProgress": "FullyGraded",
    "timestamp": datetime.utcnow().isoformat() + "Z"
}

score_url, score_payload
