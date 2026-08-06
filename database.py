import os
import json
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client, create_client
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Initialize Supabase Client centrally
def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    
    if not url or not key:
        raise ValueError(
            "❌ CRITICAL CONFIG ERROR: Missing SUPABASE_URL or SUPABASE_KEY. "
            "Please check that your .env file is properly configured in the root directory."
        )
    
    return create_client(url, key)

# Single global instance imported by all routers
supabase = get_supabase_client()
security = HTTPBearer(auto_error=False)

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Centralized authentication dependency. Retrieves the authenticated user 
    from either authorization headers or session cookies.
    """
    token = None
    
    # 1. Check Authorization Bearer Header first
    if credentials:
        token = credentials.credentials
    
    # 2. Fallback to application cookie if header is absent
    if not token:
        token = request.cookies.get("td_tokens_session")
        if token and token.startswith("{"):
            try:
                token_data = json.loads(token)
                token = token_data.get("access_token")
            except Exception:
                pass

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated: No token found.")

    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")
        
        user = user_response.user
        
        # Fetch profile data to include admin privileges, tokens, and display info
        profile_res = supabase.table("profiles").select("*").eq("id", user.id).single().execute()
        profile = profile_res.data if profile_res and profile_res.data else {}
        
        return {
            "id": user.id,
            "email": user.email,
            "full_name": profile.get("full_name", "Player"),
            "is_admin": profile.get("is_admin", False),
            "favorite_team": profile.get("favorite_team", "🏈 Free Agent / Neutral")
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication validation failed: {str(e)}")
