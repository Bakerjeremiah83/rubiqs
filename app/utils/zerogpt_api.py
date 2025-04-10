import requests
import os

def check_ai_generated_text(text):
    url = "https://api.zerogpt.com/api/v1/detectText"
    headers = {
        "Content-Type": "application/json",
        "apikey": os.getenv("ZEROGPT_API_KEY")
    }
    payload = {
        "input_text": text,
        "mode": "api"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return {
            "ai_probability": data.get("ai_probability", None),
            "verdict": data.get("verdict", "Unknown")
        }
    except Exception as e:
        return {"error": str(e)}
