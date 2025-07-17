import uuid
from lumina_care.supabase_client import supabase

def upload_file_to_supabase(file, folder='media', bucket='lumina-media'):
    filename = f"{folder}/{uuid.uuid4()}_{file.name}"
    try:
        supabase.storage.from_(bucket).upload(filename, file, {"content-type": file.content_type})
        public_url = supabase.storage.from_(bucket).get_public_url(filename)
        return public_url
    except Exception as e:
        print("Error uploading to Supabase:", e)
        return None
