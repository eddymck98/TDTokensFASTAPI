import json
from fastapi import Cookie, HTTPException, status
from utils.database import get_supabase_client

def get_current_user(td_tokens_session: str = Cookie(None)):
    """Extracts session user from the secure HTTP cookie."""
    if not td_tokens_session:
        return None
    try:
        supabase = get_supabase_client()
        session_data = json.loads(td_tokens_session)
        acc_token = session_data.get("access_token")
        ref_token = session_data.get("refresh_token")
        if acc_token and ref_token:
            res = supabase.auth.set_session(acc_token, ref_token)
            if res and res.user:
                return res.user
    except Exception:
        pass
    return None

def require_auth(td_tokens_session: str = Cookie(None)):
    """Dependency that forces a user to be logged in, otherwise throws a 401 error."""
    user = get_current_user(td_tokens_session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    return user
