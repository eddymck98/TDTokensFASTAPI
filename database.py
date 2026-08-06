import os
import json
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client, create_client

# Initialize Supabase Client
def get_supabase_client() -> Client:
    # Ensure these environment variables are set in your local environment or .env file
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
    
    return create_client(url, key)

supabase = get_supabase_client()
security = HTTPBearer(auto_error=False)

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Retrieves the authenticated user from cookies, authorization headers, or session state.
    """
    token = None
    
    # 1. Check Authorization Header first
    if credentials:
        token = credentials.credentials
    
    # 2. Fallback to cookie if header is not present
    if not token:
        token = request.cookies.get("td_tokens_session")
        if token and token.startswith("{"):
            try:
                token_data = json.loads(token)
                token = token_data.get("access_token")
            except Exception:
                pass

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        user = user_response.user
        
        # Fetch profile data to include admin status or custom flags
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
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
