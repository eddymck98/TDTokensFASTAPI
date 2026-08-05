import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def get_supabase_client() -> Client:
    """Returns an active Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Export a default instance for quick access
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
