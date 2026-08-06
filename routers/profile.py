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

@router.get("/profile", response_class=HTMLResponse)
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
        profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
        all_profiles = supabase.table("profiles").select("id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title, featured_badges, unlocked_badges, favorite_player, bio").execute().data or []
    except Exception:
        profile = {}
        all_profiles = []

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "profile": profile,
        "all_profiles": all_profiles
    })

@router.post("/profile/update")
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

@router.post("/profile/featured-badges")
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
