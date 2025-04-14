# File: app/supabase_client.py

from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(file, filename):
    try:
        path = f"{filename}"
        response = supabase.storage.from_(SUPABASE_BUCKET).upload(path, file, file_options={"content-type": file.mimetype})
        public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(path)
        return public_url
    except Exception as e:
        print("❌ Failed to upload to Supabase:", str(e))
        return None
