# release_runner.py
import requests
import os

# Make sure to use your deployed domain
url = "https://rubiqs.onrender.com/release-pending"

try:
    res = requests.get(url)
    print("✅ Release Triggered:", res.status_code, res.text)
except Exception as e:
    print("❌ Error calling release endpoint:", e)
