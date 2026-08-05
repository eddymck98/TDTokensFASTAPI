from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.database import get_supabase_client
from utils.dependencies import require_auth
from utils.helpers import get_static_nfl_team_data

router = APIRouter(tags=["Rules"])
templates = Jinja2Templates(directory="templates")
supabase = get_supabase_client()
NFL_TEAM_DATA = get_static_nfl_team_data()

@router.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request, user=Depends(require_auth)):
    """Renders the game rules, scoring breakdowns, and token mechanics info."""
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
    return templates.TemplateResponse(request=request, name="rules.html", context={
        "request": request,
        "profile": profile,
        "team_data": NFL_TEAM_DATA
    })

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user=Depends(require_auth)):
    """Renders the profile customization and trophy cabinet page."""
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
    unlocked_badges = sync_and_get_user_badges(user.id)
    
    return templates.TemplateResponse(request=request, name="profile.html", context={
        "request": request,
        "profile": profile,
        "teams": list(NFL_TEAM_DATA.keys()),
        "unlocked_badges": unlocked_badges,
        "master_badges": MASTER_BADGES,
        "available_titles": AVAILABLE_TITLES
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
    bio: str = Form("Ready for Kickoff!"),
    user=Depends(require_auth)
):
    """Saves profile modifications and custom configurations."""
    if contains_profanity(full_name) or contains_profanity(favorite_player) or contains_profanity(bio):
        return RedirectResponse(url="/profile?error=profanity", status_code=status.HTTP_303_SEE_OTHER)
        
    supabase.table("profiles").update({
        "full_name": full_name.strip(),
        "favorite_team": favorite_team,
        "selected_title": selected_title,
        "avatar_emoji": avatar_emoji,
        "avatar_border": avatar_border,
        "avatar_color": avatar_color,
        "favorite_player": favorite_player.strip(),
        "bio": bio.strip()
    }).eq("id", user.id).execute()
    
    return RedirectResponse(url="/profile?success=updated", status_code=status.HTTP_303_SEE_OTHER)
