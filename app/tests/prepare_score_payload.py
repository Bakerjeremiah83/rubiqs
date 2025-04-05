import os
import json
import uuid
from datetime import datetime

# Simulated decoded launch data
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

# Score to post
score = 92

# Prepare URL and payload
lineitem_url = launch_data["https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"]["lineitem"]
score_url = lineitem_url.split("?")[0] + "/scores"

score_payload = {
    "userId": launch_data["sub"],
    "scoreGiven": score,
    "scoreMaximum": 100,
    "activityProgress": "Completed",
    "gradingProgress": "FullyGraded",
    "timestamp": datetime.utcnow().isoformat() + "Z"
}

score_url, score_payload
