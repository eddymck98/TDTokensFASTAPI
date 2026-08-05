import json
from fastapi import APIRouter, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from utils.database import get_supabase_client
from utils.helpers import contains_profanity
from utils.email_service import send_verification_email

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")
supabase = get_supabase_client()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the login and signup page."""
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None, "msg": None})

@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Authenticates the user and sets a secure session cookie."""
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if auth_res.user and auth_res.user.email_confirmed_at:
            session_payload = json.dumps({
                "access_token": auth_res.session.access_token,
                "refresh_token": auth_res.session.refresh_token
            })
            response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="td_tokens_session", value=session_payload, max_age=2592000, httponly=True)
            return response
        else:
            supabase.auth.sign_out()
            return templates.TemplateResponse(request=request, name="login.html", context={"error": "Please authorise your email first."})
    except Exception:
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Invalid login credentials."})

@router.post("/signup", response_class=HTMLResponse)
async def signup(
    request: Request,
    first_name: str = Form(...),
    surname: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Registers a new user, creates their profile, and triggers the Resend email."""
    full_name = f"{first_name.strip()} {surname.strip()}"
    if contains_profanity(full_name):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Name contains restricted words."})
    
    try:
        res = supabase.auth.sign_up({"email": email.strip(), "password": password})
        if res.user:
            new_uid = res.user.id
            supabase.table("profiles").insert({
                "id": new_uid,
                "email": email.strip(),
                "full_name": full_name,
                "tokens": 10,
                "is_admin": False,
                "favorite_team": "🏈 Free Agent / Neutral",
                "avatar_emoji": "🏈",
                "avatar_border": "solid",
                "avatar_color": "#1e3a8a",
                "selected_title": "🏈 Gridiron Contender",
                "default_league_view": "00000000-0000-0000-0000-000000000001"
            }).execute()
            
            # Auto-join the global leaderboard
            supabase.table("league_members").insert({
                "league_id": "00000000-0000-0000-0000-000000000001",
                "user_id": new_uid
            }).execute()
            
            send_verification_email(email.strip(), "https://tdtokens.co.uk")
            return templates.TemplateResponse(request=request, name="login.html", context={"msg": f"Verification email sent to {email}. Check your inbox!"})
    except Exception as e:
        return templates.TemplateResponse(request=request, name="login.html", context={"error": f"Signup failed: {str(e)}"})

@router.get("/logout")
async def logout():
    """Destroys the session cookie and routes back to the login screen."""
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="td_tokens_session")
    return response
