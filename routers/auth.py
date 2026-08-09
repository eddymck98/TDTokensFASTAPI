import os
import json
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
import resend
from supabase import Client, create_client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Resend API Key setup from environment variables
resend.api_key = os.environ.get("RESEND_API_KEY", "")

def get_supabase(request: Request) -> Client:
    return request.app.state.supabase

def contains_profanity(text: str) -> bool:
    PROFANITY_FILTER = ["damn", "hell", "crap", "shit", "fuck", "bitch", "asshole", "dick", "cunt", "bastard"]
    if not text: return False
    text_lower = text.lower(); words = text_lower.split()
    return any(p_word in text_lower or any(p_word == w for w in words) for p_word in PROFANITY_FILTER)

def send_verification_email(to_email: str, verification_link: str) -> bool:
    try:
        html_content = f"""<div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;"><div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);"><div style="text-align: center; margin-bottom: 30px;"><h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1><p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Weekly NFL Predictions & Wagers</p></div><h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3><p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">Thanks for registering an account with Touchdown Tokens. To lock in your weekly picks, compete on leaderboards, and claim your tokens, please authorise your email address below:</p><div style="text-align: center; margin: 35px 0;"><a href="{verification_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">AUTHORISE EMAIL ADDRESS</a></div><p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">If you did not request this account creation or verification, you can safely ignore and delete this email.</p></div><div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">&copy; 2026 Touchdown Tokens. All rights reserved.</div></div>"""
        resend.Emails.send({"from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>", "to": [to_email], "subject": "🏈 Authorise Your Touchdown Tokens Account", "html": html_content})
        return True
    except Exception:
        return False

# ==========================================
# GET ROUTES FOR RENDERING TEMPLATES
# ==========================================

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Renders the user registration/signup page."""
    return templates.TemplateResponse(request=request, name="signup.html", context={"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Renders the user login page."""
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

# ==========================================
# POST ROUTES FOR FORM ACTIONS
# ==========================================

@router.post("/login")
async def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        lock_check = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 998).execute().data
        if lock_check and lock_check[0].get("winning_answer") == "LOCKED":
            return RedirectResponse(url="/auth/login?error=admin_locked", status_code=303)
    except Exception:
        pass

    try:
        auth_response = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        user = auth_response.user
        if user and user.email_confirmed_at:
            response = RedirectResponse(url="/", status_code=303)
            if auth_response.session:
                session_data = json.dumps({
                    "access_token": auth_response.session.access_token,
                    "refresh_token": auth_response.session.refresh_token
                })
                response.set_cookie(key="td_tokens_session", value=session_data, max_age=2592000, httponly=True, secure=True)
            return response
        else:
            return RedirectResponse(url="/auth/login?error=email_unverified", status_code=303)
    except Exception:
        return RedirectResponse(url="/auth/login?error=invalid_credentials", status_code=303)

@router.post("/signup")
async def signup_user(
    request: Request,
    first_name: str = Form(...),
    surname: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        lock_check = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 997).execute().data
        if lock_check and lock_check[0].get("winning_answer") == "LOCKED":
            raise HTTPException(status_code=403, detail="New account registrations are currently locked by the administrator.")
    except HTTPException as he:
        raise he
    except Exception:
        pass

    combined_full_name = f"{first_name.strip()} {surname.strip()}"
    if contains_profanity(combined_full_name):
        raise HTTPException(status_code=400, detail="Name contains restricted language.")

    try:
        response = supabase.auth.sign_up({"email": email.strip(), "password": password})
        if response.user:
            new_uid = response.user.id
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

            # Generate proper verification token link via admin api
            service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
            url = os.environ.get("SUPABASE_URL", "")
            admin_supabase = create_client(url, service_key) if service_key and url else supabase
            
            link_response = admin_supabase.auth.admin.generate_link({"type": "signup", "email": email.strip()})
            verification_link = f"https://tdtokens.co.uk/"
            
            if link_response and hasattr(link_response, "properties") and link_response.properties:
                props = link_response.properties
                action_link = props.get("action_link") if isinstance(props, dict) else getattr(props, "action_link", None)
                email_otp = props.get("email_otp") if isinstance(props, dict) else getattr(props, "email_otp", None)
                verification_link = f"https://tdtokens.co.uk/?token={email_otp}&type=signup" if email_otp else (action_link or verification_link)

            send_verification_email(email.strip(), verification_link)
            return RedirectResponse(url="/?success=signup_complete", status_code=303)
        else:
            raise HTTPException(status_code=400, detail="Sign up failed.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/logout")
async def logout_user(request: Request, supabase: Client = Depends(get_supabase)):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="td_tokens_session")
    return response

@router.post("/password-reset-request")
async def request_password_reset(
    request: Request,
    email: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        url = os.environ.get("SUPABASE_URL", "")
        admin_supabase = create_client(url, service_key) if service_key and url else supabase
        response = admin_supabase.auth.admin.generate_link({"type": "recovery", "email": email.strip()})
        
        if response and hasattr(response, "properties") and response.properties:
            props = response.properties
            action_link = props.get("action_link") if isinstance(props, dict) else getattr(props, "action_link", None)
            email_otp = props.get("email_otp") if isinstance(props, dict) else getattr(props, "email_otp", None)
            recovery_link = f"https://tdtokens.co.uk/?token={email_otp}&type=recovery" if email_otp else action_link
            
            if recovery_link:
                html_content = f"""<div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;"><div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);"><div style="text-align: center; margin-bottom: 30px;"><h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1><p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Password Reset Request</p></div><h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Reset Your Password 🔑</h3><p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">Click the secure button below to choose a brand new password for your account:</p><div style="text-align: center; margin: 35px 0;"><a href="{recovery_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">RESET PASSWORD</a></div></div></div>"""
                resend.Emails.send({"from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>", "to": [email.strip()], "subject": "🔑 Reset Your Touchdown Tokens Password", "html": html_content})
                return RedirectResponse(url="/?success=reset_sent", status_code=303)
        raise HTTPException(status_code=400, detail="Could not generate recovery link.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
