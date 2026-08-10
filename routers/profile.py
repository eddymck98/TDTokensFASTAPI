import os
import json
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import Client

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
    except Exception:
        return RedirectResponse(url="/", status_code=303)

    try:
        profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data or {}
        all_profiles = supabase.table("profiles").select("id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title, featured_badges, unlocked_badges, favorite_player, bio").execute().data or []
        
        # Calculate user progression / milestones to dynamically determine unlocked titles
        user_tokens = profile.get("tokens", 10)
        
        # Fetch total wins or bets if needed for advanced locks, or derive from token growth/history
        bets_res = supabase.table("user_bets").select("is_won").eq("user_id", user.id).execute().data or []
        total_wins = sum(1 for b in bets_res if b.get("is_won") is True)

        # Define title unlock rules mapping
        # Example criteria: "Gridiron Contender" (Default/Always), "High Roller" (20+ tokens), "Sharp Predictor" (5+ wins)
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

        # Inject unlocked titles into profile context for validation and template rendering
        profile["unlocked_titles"] = unlocked_titles

    except Exception:
        profile = {"unlocked_titles": ["🏈 Gridiron Contender"]}
        all_profiles = []

    return templates.TemplateResponse(request=request, name="profile.html", context={
        "request": request,
        "user": user,
        "profile": profile,
        "all_profiles": all_profiles
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
        supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
        user = supabase.auth.get_user().user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    if not full_name.strip():
        raise HTTPException(status_code=400, detail="Display name cannot be blank.")

    # Validate that the selected title is actually unlocked by the user to prevent tampering
    try:
        profile_data = supabase.table("profiles").select("tokens, is_admin").eq("id", user.id).single().execute().data or {}
        user_tokens = profile_data.get("tokens", 10)
        is_admin = profile_data.get("is_admin", False)
        
        bets_res = supabase.table("user_bets").select("is_won").eq("user_id", user.id).execute().data or []
        total_wins = sum(1 for b in bets_res if b.get("is_won") is True)

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
        pass # Fallback safety if verification fails lookup

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

        return RedirectResponse(url="/profile?success=profile_updated", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
        user = supabase.auth.get_user().user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    form_data = await request.form()
    # Extract list of featured badges from multiselect form inputs
    featured_badges = form_data.getlist("featured_badges")

    if len(featured_badges) > 3:
        raise HTTPException(status_code=400, detail="You can select a maximum of 3 featured badges.")

    try:
        supabase.table("profiles").update({
            "featured_badges": featured_badges
        }).eq("id", user.id).execute()

        return RedirectResponse(url="/profile?success=badges_updated", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
