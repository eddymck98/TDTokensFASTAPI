from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.database import get_supabase_client
from utils.dependencies import require_auth
from utils.helpers import contains_profanity, get_static_nfl_team_data
import random
import string

router = APIRouter(tags=["Leagues"])
templates = Jinja2Templates(directory="templates")
supabase = get_supabase_client()
NFL_TEAM_DATA = get_static_nfl_team_data()

@router.get("/leagues", response_class=HTMLResponse)
async def leagues_page(request: Request, user=Depends(require_auth)):
    """Renders mini-league standings, join/create forms, and trash talk feeds."""
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
    
    # Fetch user memberships
    my_memberships = supabase.table("league_members").select("league_id, leagues(id, league_name, invite_code, created_by)").eq("user_id", user.id).execute().data
    all_my_leagues = [m for m in my_memberships if m.get("leagues")]
    
    # Fetch global leaderboard data
    profiles_res = supabase.table("profiles").select("*").order("tokens", desc=True).execute()

    return templates.TemplateResponse(request=request, name="leagues.html", context={
        "request": request,
        "profile": profile,
        "my_leagues": all_my_leagues,
        "leaderboard": profiles_res.data if profiles_res.data else []
    })

@router.post("/leagues/create")
async def create_league(
    request: Request,
    league_name: str = Form(...),
    league_password: str = Form(""),
    user=Depends(require_auth)
):
    """Creates a custom mini-league with a unique 6-character invite code."""
    if contains_profanity(league_name):
        return RedirectResponse(url="/leagues?error=profanity", status_code=status.HTTP_303_SEE_OTHER)
        
    invite_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    try:
        res = supabase.table("leagues").insert({
            "league_name": league_name.strip(),
            "invite_code": invite_code,
            "created_by": user.id,
            "league_password": league_password.strip()
        }).execute()
        
        if res.data:
            supabase.table("league_members").insert({
                "league_id": res.data[0]["id"],
                "user_id": user.id
            }).execute()
    except Exception:
        pass
        
    return RedirectResponse(url="/leagues?success=created", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/leagues/join")
async def join_league(
    request: Request,
    invite_code: str = Form(...),
    league_password: str = Form(""),
    user=Depends(require_auth)
):
    """Allows players to join a mini-league using an invite code and passcode."""
    clean_code = invite_code.strip().upper()
    found = supabase.table("leagues").select("id, league_name, league_password").eq("invite_code", clean_code).execute().data
    
    if not found:
        return RedirectResponse(url="/leagues?error=invalid_code", status_code=status.HTTP_303_SEE_OTHER)
        
    target = found[0]
    if target.get("league_password", "") and target.get("league_password", "") != league_password.strip():
        return RedirectResponse(url="/leagues?error=wrong_password", status_code=status.HTTP_303_SEE_OTHER)
        
    # Check if already a member
    existing = supabase.table("league_members").select("id").eq("league_id", target["id"]).eq("user_id", user.id).execute().data
    if not existing:
        supabase.table("league_members").insert({
            "league_id": target["id"],
            "user_id": user.id
        }).execute()
        
    return RedirectResponse(url="/leagues?success=joined", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/leagues/chat")
async def post_trash_talk(
    request: Request,
    league_id: str = Form(...),
    message: str = Form(...),
    user=Depends(require_auth)
):
    """Posts a message to a mini-league chat feed."""
    if not message.strip():
        return RedirectResponse(url="/leagues", status_code=status.HTTP_303_SEE_OTHER)
        
    if contains_profanity(message):
        return RedirectResponse(url="/leagues?error=profanity", status_code=status.HTTP_303_SEE_OTHER)
        
    supabase.table("trash_talk").insert({
        "user_id": user.id,
        "league_id": league_id,
        "message": message.strip()
    }).execute()
    
    return RedirectResponse(url="/leagues", status_code=status.HTTP_303_SEE_OTHER)
