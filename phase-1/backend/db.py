import os
from supabase import create_client, Client

class SupabaseClient:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials not found in environment variables.")
        self.client: Client = create_client(url, key)

    def upload_file(self, file_obj, filename):
        """Uploads a file to the 'uploads' bucket."""
        bucket_name = "uploads"
        # Reading file content; assumption: file_obj is a file-like object (bytes)
        file_content = file_obj.read()
        response = self.client.storage.from_(bucket_name).upload(path=filename, file=file_content)
        
        # Get public URL
        # Note: Depending on bucket privacy, create_signed_url might be needed. 
        # For this phase, assuming public bucket or we just store the path.
        # But let's try to get a public URL if possible, or just return the path.
        public_url = self.client.storage.from_(bucket_name).get_public_url(filename)
        return public_url

    def create_order(self, order_data):
        """Inserts an order into the 'orders' table."""
        response = self.client.table("orders").insert(order_data).execute()
        return response.data

_client_instance = None

def get_supabase_client():
    global _client_instance
    if _client_instance is None:
        _client_instance = SupabaseClient()
    return _client_instance
