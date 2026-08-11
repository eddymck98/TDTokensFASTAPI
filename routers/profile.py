import os
import json
from typing import Optional
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import Client
from database import NFL_TEAM_DATA

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_supabase(request: Request) -> Client:
    return request.app.state.supabase

@router.get("/", response_class=HTMLResponse)
async def get_profile_page(request: Request, supabase: Client = Depends(get_supabase)):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        ref_token = token_data.get("refresh_token")
        
        auth_res = supabase.auth.set_session(acc_token, ref_token)
        user = auth_res.user
        if not user:
            return RedirectResponse(url="/", status_code=303)
            
        supabase.postgrest.auth(acc_token)
    except Exception:
        return RedirectResponse(url="/", status_code=303)

    try:
        # Fetch current user profile row
        profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
        profile = profile_res.data[0] if profile_res.data else {}

        all_profiles = supabase.table("profiles").select("id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title, featured_badges, unlocked_badges, favorite_player, bio").execute().data or []
        
        user_tokens = profile.get("tokens", 10)
        
        # Calculate total wins using tokens_awarded > 0 from user_bets
        total_wins = 0
        try:
            bets_res = supabase.table("user_bets").select("tokens_awarded").eq("user_id", user.id).execute().data or []
            for b in bets_res:
                if (b.get("tokens_awarded") or 0) > 0:
                    total_wins += 1
        except Exception:
            pass 

        # Define title unlock rules mapping
        unlocked_titles = ["🏈 Gridiron Contender", "Free Agent"] # Default basic titles
        
        if user_tokens >= 15:
            unlocked_titles.append("💰 High Roller")
        if user_tokens >= 25:
            unlocked_titles.append("🔥 Token Tycoon")
        if total_wins >= 3:
            unlocked_titles.append("🎯 Sharp Predictor")
        if total_wins >= 10:
            unlocked_titles.append("🧠 Gridiron Oracle")
        if profile.get("is_admin"):
            unlocked_titles.append("👑 Commissioner")

        profile["unlocked_titles"] = unlocked_titles

        # Fetch trophies ONLY earned within the user's mini-leagues context
        user_leagues = supabase.table("league_members").select("league_id").eq("user_id", user.id).execute().data
        league_ids = [l["league_id"] for l in user_leagues] if user_leagues else []

        trophies = []
        if league_ids:
            trophies_res = supabase.table("trophies") \
                .select("*") \
                .in_("league_id", league_ids) \
                .eq("user_id", user.id) \
                .execute()
            trophies = trophies_res.data or []
        else:
            trophies = []

    except Exception as e:
        print(f"Profile fetch error: {e}")
        profile = {"unlocked_titles": ["🏈 Gridiron Contender", "Free Agent"]}
        all_profiles = []
        trophies = []

    return templates.TemplateResponse(request=request, name="profile.html", context={
        "request": request,
        "user": user,
        "profile": profile,
        "all_profiles": all_profiles,
        "trophies": trophies,
        "team_data": NFL_TEAM_DATA
    })

@router.post("/update")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    favorite_team: str = Form(...),
    selected_title: str = Form(...),
    avatar_emoji: str = Form(...),
    avatar_border: str = Form(...),
    avatar_color: str = Form(...),
    favorite_player: str = Form(""),
    bio: str = Form(""),
    supabase: Client = Depends(get_supabase)
):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        supabase.auth.set_session(acc_token, token_data.get("refresh_token"))
        supabase.postgrest.auth(acc_token)
        
        user = supabase.auth.get_user().user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    if not full_name.strip():
        raise HTTPException(status_code=400, detail="Display name cannot be blank.")

    try:
        profile_data_res = supabase.table("profiles").select("tokens, is_admin").eq("id", user.id).execute()
        profile_data = profile_data_res.data[0] if profile_data_res.data else {}
        user_tokens = profile_data.get("tokens", 10)
        is_admin = profile_data.get("is_admin", False)
        
        total_wins = 0
        try:
            bets_res = supabase.table("user_bets").select("tokens_awarded").eq("user_id", user.id).execute().data or []
            for b in bets_res:
                if (b.get("tokens_awarded") or 0) > 0:
                    total_wins += 1
        except Exception:
            pass

        allowed_titles = ["🏈 Gridiron Contender", "Free Agent"]
        if user_tokens >= 15:
            allowed_titles.append("💰 High Roller")
        if user_tokens >= 25:
            allowed_titles.append("🔥 Token Tycoon")
        if total_wins >= 3:
            allowed_titles.append("🎯 Sharp Predictor")
        if total_wins >= 10:
            allowed_titles.append("🧠 Gridiron Oracle")
        if is_admin:
            allowed_titles.append("👑 Commissioner")

        if selected_title.strip() not in allowed_titles:
            raise HTTPException(status_code=400, detail="You have not unlocked this title yet!")

    except HTTPException as he:
        raise he
    except Exception:
        pass 

    try:
        supabase.table("profiles").update({
            "full_name": full_name.strip(),
            "favorite_team": favorite_team.strip(),
            "selected_title": selected_title.strip(),
            "avatar_emoji": avatar_emoji.strip(),
            "avatar_border": avatar_border.strip(),
            "avatar_color": avatar_color.strip(),
            "favorite_player": favorite_player.strip(),
            "bio": bio.strip()
        }).eq("id", user.id).execute()

        return RedirectResponse(url="/profile/?success=profile_updated", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/update-email")
async def update_email(
    request: Request,
    new_email: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        supabase.auth.set_session(acc_token, token_data.get("refresh_token"))
        
        user = supabase.auth.get_user().user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")

        # Request Supabase Auth to update user email
        supabase.auth.update_user({"email": new_email.strip()})
        
        return RedirectResponse(url="/profile?success=email_update_sent", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/profile?error={str(e)}", status_code=303)

@router.post("/featured-badges")
async def update_featured_badges(
    request: Request,
    supabase: Client = Depends(get_supabase)
):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        supabase.auth.set_session(acc_token, token_data.get("refresh_token"))
        supabase.postgrest.auth(acc_token)
        
        user = supabase.auth.get_user().user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    form_data = await request.form()
    featured_badges = form_data.getlist("featured_badges")

    if len(featured_badges) > 3:
        raise HTTPException(status_code=400, detail="You can select a maximum of 3 featured badges.")

    try:
        supabase.table("profiles").update({
            "featured_badges": featured_badges
        }).eq("id", user.id).execute()

        return RedirectResponse(url="/profile/?success=badges_updated", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/notifications")
async def update_notification_preferences(
    request: Request,
    email_notifications: Optional[str] = Form(None),
    grading_emails: Optional[str] = Form(None),
    supabase: Client = Depends(get_supabase)
):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        supabase.auth.set_session(acc_token, token_data.get("refresh_token"))
        supabase.postgrest.auth(acc_token)
        
        user = supabase.auth.get_user().user
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)
    except Exception:
        return RedirectResponse(url="/auth/login", status_code=303)

    is_email_notif = True if email_notifications == "true" else False
    is_grading_notif = True if grading_emails == "true" else False

    try:
        supabase.table("profiles").update({
            "email_notifications": is_email_notif,
            "grading_emails": is_grading_notif
        }).eq("id", user.id).execute()

        return RedirectResponse(url="/profile/?success=preferences_saved", status_code=303)
    except Exception as e:
        print(f"Error saving preferences: {e}")
        return RedirectResponse(url="/profile/?error=save_failed", status_code=303)
