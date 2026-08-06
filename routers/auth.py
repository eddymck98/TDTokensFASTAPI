import json
import os
from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client

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
async def handle_login(request: Request, email: str = Form(...), password: str = Form(...)):
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

            try:
                supabase.table("league_members").insert({
                    "league_id": "00000000-0000-0000-0000-000000000001",
                    "user_id": new_uid
                }).execute()
            except Exception:
                pass

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


@router.post("/forgot-password")
async def handle_forgot_password(email: str = Form(...)):
    """Generates and emails password reset links matching app.py logic."""
    try:
        service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        url = os.environ.get("SUPABASE_URL", "")
        admin_supabase = create_client(url, service_key) if service_key and url else supabase
        
        response = admin_supabase.auth.admin.generate_link({"type": "recovery", "email": email.strip()})
        if response and hasattr(response, "properties") and response.properties:
            props = response.properties
            action_link = props.get("action_link") if isinstance(props, dict) else getattr(props, "action_link", None)
            email_otp = props.get("email_otp") if isinstance(props, dict) else getattr(props, "email_otp", None)
            recovery_link = f"https://tdtokens.co.uk/auth/reset-password?token={email_otp}&type=recovery" if email_otp else action_link

            if recovery_link:
                # Custom Resend Email HTML matching app.py
                html_content = f"""<div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;"><div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);"><h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Reset Your Password 🔑</h3><p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">Click the secure button below to choose a brand new password for your account:</p><div style="text-align: center; margin: 35px 0;"><a href="{recovery_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; display: inline-block;">RESET PASSWORD</a></div></div></div>"""
                import resend
                resend.Emails.send({"from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>", "to": [email.strip()], "subject": "🔑 Reset Your Touchdown Tokens Password", "html": html_content})
                return RedirectResponse(url="/auth/login?msg=Reset+Link+Sent", status_code=303)
        raise HTTPException(status_code=400, detail="Could not generate recovery link.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error sending reset email: {str(e)}")


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
