# services/supabase_storage.py
import uuid
from supabase import create_client
from decouple import config

SUPABASE_URL = config("SUPABASE_URL")
SUPABASE_KEY = config("SUPABASE_KEY")
SUPABASE_BUCKET = config("SUPABASE_BUCKET", default="lumina-media")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class SupabaseStorageService:
    def __init__(self, bucket_name=SUPABASE_BUCKET):
        self.bucket_name = bucket_name
        self.client = supabase.storage.from_(self.bucket_name)

    def upload_file(self, file, folder="uploads"):
        """Uploads a file and returns its public URL."""
        filename = f"{folder}/{uuid.uuid4()}_{file.name}"
        try:
            # Upload the file
            self.client.upload(filename, file, {"content-type": file.content_type})

            # Get the public URL
            return self.client.get_public_url(filename)
        except Exception as e:
            print("Upload failed:", e)
            return None

    def delete_file(self, path):
        """Deletes a file at the given path."""
        try:
            result = self.client.remove([path])
            return result
        except Exception as e:
            print("Delete failed:", e)
            return None

    def list_files(self, prefix=""):
        """Lists files in the given folder/prefix."""
        try:
            return self.client.list(prefix)
        except Exception as e:
            print("List failed:", e)
            return []
