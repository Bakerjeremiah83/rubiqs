from supabase import create_client
import os
from datetime import datetime

def upload_to_supabase(file, file_name):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    name, ext = os.path.splitext(file_name)
    new_file_name = f"{name}_{timestamp}{ext}"

    file_path = f"rubrics/{new_file_name}"
    print(f"🆕 Uploading as: {file_path}")

    # Read the file content
    file_content = file.read()

    res = supabase.storage.from_("rubrics").upload(file_path, file_content)

    # Correct way to check for an error:
    if hasattr(res, "error") and res.error:
        raise Exception(f"Upload failed: {res.error['message']}")

    public_url = f"{url}/storage/v1/object/public/rubrics/{new_file_name}"
    return public_url
