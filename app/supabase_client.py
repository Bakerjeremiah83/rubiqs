# File: app/supabase_client.py
from supabase import create_client
from dotenv import load_dotenv
import os
import mimetypes

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(file, filename):
    try:
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        result = supabase.storage.from_("rubrics").upload(
            path=filename,
            file=file,
            file_options={"content-type": content_type},
            upsert=True
        )
        public_url = supabase.storage.from_("rubrics").get_public_url(filename)
        return public_url
    except Exception as e:
        print("❌ Failed to upload to Supabase:", str(e))
        return None
