import json
from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from utils.database import supabase
from utils.email_service import send_verification_email
from utils.helpers import contains_profanity

router = APIRouter(prefix="/auth", tags=["Auth"])
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Renders the login and sign-up page matching app.py logic."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def handle_login(request: Response, email: str = Form(...), password: str = Form(...)):
    """Handles user sign-in and session cookie storage matching app.py."""
    try:
        # Check sign-in lock state
        signin_lock_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 998).execute().data
        is_signin_locked = signin_lock_res[0]["winning_answer"] == "LOCKED" if signin_lock_res else False
        
        if is_signin_locked:
            raise HTTPException(status_code=403, detail="SIGN-IN LOCKED: The Admin has temporarily disabled log-ins.")

        auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = auth_response.user
        
        if user and user.email_confirmed_at:
            response = RedirectResponse(url="/", status_code=303)
            if auth_response.session:
                session_data = json.dumps({
                    "access_token": auth_response.session.access_token,
                    "refresh_token": auth_response.session.refresh_token
                })
                # Set cookie matching app.py controller logic (30 days max_age)
                response.set_cookie(key="td_tokens_session", value=session_data, max_age=2592000, httponly=True)
            return response
        else:
            supabase.auth.sign_out()
            raise HTTPException(status_code=400, detail="Please authorise your email first before logging in.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Login failed: {str(e)}")


@router.post("/signup")
async def handle_signup(
    first_name: str = Form(...),
    surname: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Handles new user registration, profile creation, and verification email trigger matching app.py."""
    try:
        # Check sign-up lock state
        signup_lock_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 997).execute().data
        is_signup_locked = signup_lock_res[0]["winning_answer"] == "LOCKED" if signup_lock_res else False

        if is_signup_locked:
            raise HTTPException(status_code=403, detail="SIGN-UP LOCKED: The Admin has temporarily disabled new account registrations.")

        combined_full_name = f"{first_name.strip()} {surname.strip()}"
        if contains_profanity(combined_full_name):
            raise HTTPException(status_code=400, detail="Your name contains restricted language.")

        response = supabase.auth.sign_up({"email": email.strip(), "password": password})
        if response.user:
            new_uid = response.user.id
            
            # Insert profile row with default settings matching app.py
            supabase.table("profiles").insert({
                "id": new_uid,
                "email": email.strip(),
                "full_name": combined_full_name,
                "tokens": 10,
                "is_admin": False,
                "favorite_team": "🏈 Free Agent / Neutral",
                "bio": "Ready for Kickoff!",
                "avatar_emoji": "🏈",
                "featured_badges": [],
                "unlocked_badges": [],
                "avatar_border": "solid",
                "favorite_player": "",
                "avatar_color": "#1e3a8a",
                "selected_title": "🏈 Gridiron Contender",
                "default_league_view": "00000000-0000-0000-0000-000000000001",
                "email_notifications": True,
                "high_contrast_mode": False,
                "reduced_motion": False
            }).execute()

            # Add user to global league membership table
            try:
                supabase.table("league_members").insert({
                    "league_id": "00000000-0000-0000-0000-000000000001",
                    "user_id": new_uid
                }).execute()
            except Exception:
                pass

            # Send verification email via Resend
            send_verification_email(email.strip(), "https://tdtokens.co.uk")
            
            try:
                supabase.auth.sign_out()
            except Exception:
                pass

            return RedirectResponse(url="/auth/login?msg=Account+Created+Please+Verify+Email", status_code=303)
        else:
            raise HTTPException(status_code=400, detail="Sign up failed.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sign up error: {str(e)}")


@router.get("/logout")
async def handle_logout():
    """Clears session cookie and signs out user matching app.py session cleanup."""
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="td_tokens_session")
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    return response
