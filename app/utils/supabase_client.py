from supabase import create_client
import os

def upload_to_supabase(file, file_name):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)

    file_path = f"rubrics/{file_name}"
    res = supabase.storage.from_("rubrics").upload(file_path, file)
    public_url = f"{url}/storage/v1/object/public/rubrics/{file_path}"
    return public_url
