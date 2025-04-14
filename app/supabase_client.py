# File: app/supabase_client.py
from supabase import create_client
from dotenv import load_dotenv
import os
import mimetypes

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(file_path, file_name):
    try:
        content_type, _ = mimetypes.guess_type(file_name)
        content_type = content_type or "application/octet-stream"

        with open(file_path, "rb") as f:
            data = f.read()

        supabase.storage.from_("rubrics").upload(
            file_name,
            data,
            {"content-type": content_type}
        )

        public_url = f"{SUPABASE_URL}/storage/v1/object/public/rubrics/{file_name}"
        return public_url
    except Exception as e:
        print("❌ Failed to upload to Supabase:", str(e))
        return None

