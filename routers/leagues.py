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
async def get_leagues_page(request: Request, supabase: Client = Depends(get_supabase)):
    # Session verification logic matching main.py cookie management
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

    # Fetch user profile, joined leagues, and global stats
    try:
        profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
        memberships = supabase.table("league_members").select("league_id, leagues(id, league_name, invite_code, created_by)").eq("user_id", user.id).execute().data
        all_my_leagues = [m for m in memberships if m.get("leagues")]
        
        profiles_res = supabase.table("profiles").select("id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title, featured_badges, unlocked_badges").execute()
        all_profiles = profiles_res.data if profiles_res.data else []
    except Exception:
        profile = {}
        all_my_leagues = []
        all_profiles = []

    return templates.TemplateResponse(request=request, name="leagues.html", context={
        "request": request,
        "user": user,
        "profile": profile,
        "all_my_leagues": all_my_leagues,
        "all_profiles": all_profiles
    })

@router.post("/create")
async def create_league(
    request: Request,
    league_name: str = Form(...),
    league_password: str = Form(""),
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

    if not league_name.strip():
        raise HTTPException(status_code=400, detail="League name cannot be blank.")

    import random, string
    invite_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    try:
        res_l = supabase.table("leagues").insert({
            "league_name": league_name.strip(),
            "invite_code": invite_code,
            "created_by": user.id,
            "league_password": league_password.strip() if league_password else ""
        }).execute()
        
        if res_l.data:
            new_league_id = res_l.data[0]["id"]
            supabase.table("league_members").insert({
                "league_id": new_league_id,
                "user_id": user.id
            }).execute()

        return RedirectResponse(url="/leagues?success=league_created", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/join")
async def join_league(
    request: Request,
    invite_code: str = Form(...),
    league_password: str = Form(""),
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

    clean_code = invite_code.strip().upper()
    if not clean_code:
        raise HTTPException(status_code=400, detail="Invite code cannot be blank.")

    try:
        found_league = supabase.table("leagues").select("id, league_name, league_password").eq("invite_code", clean_code).execute().data
        if not found_league:
            raise HTTPException(status_code=404, detail="Invalid invite code.")

        target_league = found_league[0]
        if target_league.get("league_password", "") and target_league.get("league_password", "") != league_password.strip():
            raise HTTPException(status_code=403, detail="Incorrect league password.")

        already_member = supabase.table("league_members").select("id").eq("league_id", target_league["id"]).eq("user_id", user.id).execute().data
        if already_member:
            return RedirectResponse(url="/leagues?info=already_member", status_code=303)

        supabase.table("league_members").insert({
            "league_id": target_league["id"],
            "user_id": user.id
        }).execute()

        return RedirectResponse(url="/leagues?success=joined_league", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/chat")
async def post_trash_talk(
    request: Request,
    league_id: str = Form(...),
    message: str = Form(...),
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

    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be blank.")

    try:
        supabase.table("trash_talk").insert({
            "user_id": user.id,
            "message": message.strip(),
            "league_id": league_id
        }).execute()

        return RedirectResponse(url=f"/leagues?success=message_posted", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
