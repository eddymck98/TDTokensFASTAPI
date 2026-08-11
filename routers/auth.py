import os
import json
from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
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
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: 'Segoe UI', Arial, sans-serif;">
          <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed; background-color: #0b0f19; padding: 40px 0;">
            <tr>
              <td align="center">
                <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #0f172a; border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                  <tr>
                    <td align="center" style="padding: 40px 30px 20px 30px;">
                      <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" width="130" style="display: block; max-width: 130px; height: auto; margin-bottom: 15px;">
                      <h1 style="font-family: Arial, sans-serif; color: #fbbf24; font-size: 28px; letter-spacing: 2px; margin: 0; text-transform: uppercase;">TOUCHDOWN TOKENS</h1>
                      <p style="color: #93c5fd; font-size: 13px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px; margin-bottom: 0;">Weekly NFL Predictions & Wagers</p>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 20px 40px 40px 40px; color: #cbd5e1; font-size: 15px; line-height: 1.6;">
                      <h3 style="color: #ffffff; font-size: 20px; margin-top: 0; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3>
                      <p style="margin-bottom: 25px;">Thanks for registering an account with Touchdown Tokens. To lock in your weekly picks, compete on leaderboards, and claim your tokens, please authorise your email address below:</p>
                      <table border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                          <td align="center" style="padding: 10px 0 25px 0;">
                            <a href="{verification_link}" target="_blank" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 30px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">AUTHORISE EMAIL ADDRESS</a>
                          </td>
                        </tr>
                      </table>
                      <p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 25px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px; margin-bottom: 0;">If you did not request this account creation or verification, you can safely ignore and delete this email.</p>
                    </td>
                  </tr>
                  <tr>
                    <td align="center" style="padding: 20px; background-color: #070a12; color: #64748b; font-size: 12px;">
                      &copy; 2026 Touchdown Tokens. All rights reserved.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """
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

@router.get("/verify", response_class=HTMLResponse)
async def verify_user_email(
    request: Request,
    token: str = Query(...),
    type: str = Query("signup"),
    supabase: Client = Depends(get_supabase)
):
    """Handles verification when a user clicks the authorization link in their email."""
    try:
        res = supabase.auth.verify_otp({"token_hash": token, "type": type})
        if res and res.session:
            response = RedirectResponse(url="/auth/login?verified=true", status_code=303)
            session_data = json.dumps({
                "access_token": res.session.access_token,
                "refresh_token": res.session.refresh_token
            })
            response.set_cookie(key="td_tokens_session", value=session_data, max_age=2592000, httponly=True, secure=True)
            return response
        else:
            return RedirectResponse(url="/auth/login?error=invalid_token", status_code=303)
    except Exception:
        return RedirectResponse(url="/auth/login?error=verification_failed", status_code=303)

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
            return RedirectResponse(url="/auth/login?error=admin_locked", status_code=303)
    except Exception:
        pass

    combined_full_name = f"{first_name.strip()} {surname.strip()}"
    if contains_profanity(combined_full_name):
        return RedirectResponse(url="/auth/login?error=profanity", status_code=303)

    clean_email = email.strip().lower()

    try:
        service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        url = os.environ.get("SUPABASE_URL", "")
        admin_supabase = create_client(url, service_key) if service_key and url else supabase

        create_res = admin_supabase.auth.admin.create_user({
            "email": clean_email,
            "password": password,
            "email_confirm": False
        })

        if create_res and create_res.user:
            new_uid = create_res.user.id
            
            admin_supabase.table("profiles").upsert({
                "id": new_uid,
                "email": clean_email,
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
                admin_supabase.table("league_members").insert({
                    "league_id": "00000000-0000-0000-0000-000000000001",
                    "user_id": new_uid
                }).execute()
            except Exception:
                pass

            link_response = admin_supabase.auth.admin.generate_link({"type": "signup", "email": clean_email})
            verification_link = "https://tdtokens.co.uk/"
            
            if link_response and hasattr(link_response, "properties") and link_response.properties:
                props = link_response.properties
                hashed_token = props.get("hashed_token") if isinstance(props, dict) else getattr(props, "hashed_token", None)
                email_otp = props.get("email_otp") if isinstance(props, dict) else getattr(props, "email_otp", None)
                token_to_use = hashed_token or email_otp
                verification_link = f"https://tdtokens.co.uk/auth/verify?token={token_to_use}&type=signup" if token_to_use else verification_link

            send_verification_email(clean_email, verification_link)
            return RedirectResponse(url="/auth/login?reset=sent", status_code=303)
        else:
            return RedirectResponse(url="/auth/login?error=signup_failed", status_code=303)
    except Exception as e:
        err_msg = str(e).lower()
        if "already registered" in err_msg or "already exists" in err_msg or "duplicate" in err_msg:
            return RedirectResponse(url="/auth/login?error=email_exists", status_code=303)
        return RedirectResponse(url="/auth/login?error=signup_failed", status_code=303)

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
            hashed_token = props.get("hashed_token") if isinstance(props, dict) else getattr(props, "hashed_token", None)
            email_otp = props.get("email_otp") if isinstance(props, dict) else getattr(props, "email_otp", None)
            token_to_use = hashed_token or email_otp
            
            recovery_link = f"https://tdtokens.co.uk/auth/login?token={token_to_use}&type=recovery" if token_to_use else f"https://tdtokens.co.uk/auth/login"
            
            if recovery_link:
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                  <meta charset="utf-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1.0">
                </head>
                <body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: 'Segoe UI', Arial, sans-serif;">
                  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed; background-color: #0b0f19; padding: 40px 0;">
                    <tr>
                      <td align="center">
                        <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #0f172a; border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                          <tr>
                            <td align="center" style="padding: 40px 30px 20px 30px;">
                              <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" width="130" style="display: block; max-width: 130px; height: auto; margin-bottom: 15px;">
                              <h1 style="font-family: Arial, sans-serif; color: #fbbf24; font-size: 28px; letter-spacing: 2px; margin: 0; text-transform: uppercase;">TOUCHDOWN TOKENS</h1>
                              <p style="color: #93c5fd; font-size: 13px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px; margin-bottom: 0;">Password Reset Request</p>
                            </td>
                          </tr>
                          <tr>
                            <td style="padding: 20px 40px 40px 40px; color: #cbd5e1; font-size: 15px; line-height: 1.6;">
                              <h3 style="color: #ffffff; font-size: 20px; margin-top: 0; margin-bottom: 15px;">Reset Your Password 🔑</h3>
                              <p style="margin-bottom: 25px;">Click the secure button below to choose a brand new password for your account:</p>
                              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                  <td align="center" style="padding: 10px 0 25px 0;">
                                    <a href="{recovery_link}" target="_blank" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 30px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">RESET PASSWORD</a>
                                  </td>
                                </tr>
                              </table>
                              <p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 25px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px; margin-bottom: 0;">If you did not request this password reset, you can safely ignore this email.</p>
                            </td>
                          </tr>
                          <tr>
                            <td align="center" style="padding: 20px; background-color: #070a12; color: #64748b; font-size: 12px;">
                              &copy; 2026 Touchdown Tokens. All rights reserved.
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>
                </body>
                </html>
                """
                resend.Emails.send({"from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>", "to": [email.strip()], "subject": "🔑 Reset Your Touchdown Tokens Password", "html": html_content})
                return RedirectResponse(url="/auth/login?reset=sent", status_code=303)
        return RedirectResponse(url="/auth/login?error=signup_failed", status_code=303)
    except Exception:
        return RedirectResponse(url="/auth/login?error=signup_failed", status_code=303)

@router.post("/update-password")
async def update_password(
    request: Request,
    new_password: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    """Handles updating the user's password once they are authenticated or come back via recovery session token."""
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        
        # Set session context so Supabase knows precisely which user account to modify
        supabase.auth.set_session(acc_token, token_data.get("refresh_token"))
        supabase.postgrest.auth(acc_token)
        
        # Execute password update
        supabase.auth.update_user({"password": new_password.strip()})
        
        return RedirectResponse(url="/profile/?success=password_updated", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
