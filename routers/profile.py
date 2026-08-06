from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from utils.database import supabase
from utils.dependencies import get_current_user
from utils.helpers import (
    AVATAR_OPTIONS,
    AVAILABLE_TITLES,
    BORDER_STYLE_OPTIONS,
    MASTER_BADGES,
    NFL_TEAM_DATA,
    contains_profanity,
)

router = APIRouter(prefix="/profile", tags=["Profile"])
templates = Jinja2Templates(directory="templates")

NFL_TEAMS = list(NFL_TEAM_DATA.keys())


def sync_and_get_user_badges(target_user_id: str) -> List[str]:
    """Syncs and evaluates the user's unlocked badges matching app.py."""
    try:
        p_data = supabase.table("profiles").select("tokens, unlocked_badges").eq("id", target_user_id).single().execute().data
        if not p_data:
            return []
    except Exception:
        return []

    toks = p_data.get("tokens", 10)
    existing_unlocked = p_data.get("unlocked_badges") if isinstance(p_data.get("unlocked_badges"), list) else []
    u_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", target_user_id).execute().data
    u_td = supabase.table("touchdown_picks").select("*").eq("user_id", target_user_id).eq("is_correct", True).order("week_number").execute().data

    newly_earned = set(existing_unlocked)
    if supabase.table("leagues").select("id").eq("created_by", target_user_id).execute().data or p_data.get("is_admin"):
        newly_earned.add("⭐ League Commissioner")
    if any(b["wager_amount"] >= 10 for b in u_bets):
        newly_earned.add("🎯 High Roller")
    if len(u_td) >= 5:
        newly_earned.add("🏈 TD Guru")
    if len(u_td) >= 9:
        newly_earned.add("🎯 Sniper")
    if len(u_td) >= 13:
        newly_earned.add("⚡ Gridiron Prophet")
    if toks == 0:
        newly_earned.add("📉 Down Bad")

    my_joined_leagues = supabase.table("league_members").select("league_id").eq("user_id", target_user_id).execute().data
    joined_l_ids = [m["league_id"] for m in my_joined_leagues] if my_joined_leagues else []
    if len(joined_l_ids) >= 3:
        newly_earned.add("🎩 Commissioner's Right Hand")

    final_badges_list = list(newly_earned)
    if set(final_badges_list) != set(existing_unlocked):
        try:
            supabase.table("profiles").update({"unlocked_badges": final_badges_list}).eq("id", target_user_id).execute()
        except Exception:
            pass

    return final_badges_list


def get_earned_title(target_user_id: str) -> str:
    """Evaluates the highest earned nametag title matching app.py."""
    try:
        prof_res = supabase.table("profiles").select("selected_title").eq("id", target_user_id).single().execute().data
        if prof_res and prof_res.get("selected_title") in AVAILABLE_TITLES:
            return prof_res.get("selected_title")
    except Exception:
        pass
    user_badges = sync_and_get_user_badges(target_user_id)
    for title, info in AVAILABLE_TITLES.items():
        if info["badge"] and info["badge"] in user_badges:
            return title
    return "🏈 Gridiron Contender"


@router.get("/", response_class=HTMLResponse)
async def view_profile_page(
    request: Request,
    view_player_id: Optional[str] = None,
    user_auth: dict = Depends(get_current_user)
):
    """Renders the comprehensive Profile, Customization, and Trophy Cabinet Hub matching app.py."""
    user_id = user_auth["id"]
    profile_res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = profile_res.data if profile_res and profile_res.data else {}

    # Target player for trophy cabinet inspection
    target_player_id = view_player_id or user_id
    target_player_res = supabase.table("profiles").select("*").eq("id", target_player_id).single().execute()
    target_player = target_player_res.data if target_player_res and target_player_res.data else profile

    all_league_profiles = supabase.table("profiles").select("id, full_name, favorite_team, avatar_emoji, unlocked_badges").execute().data or []

    # Unlocked titles calculation
    user_badges_for_titles = sync_and_get_user_badges(user_id)
    unlocked_title_options = []
    locked_title_info = []
    
    for title_name, info in AVAILABLE_TITLES.items():
        if info["badge"] is None or info["badge"] in user_badges_for_titles:
            unlocked_title_options.append(title_name)
        else:
            locked_title_info.append((title_name, info["req"]))

    curr_selected_title = profile.get("selected_title", "🏈 Gridiron Contender")
    if curr_selected_title not in unlocked_title_options:
        curr_selected_title = unlocked_title_options[0] if unlocked_title_options else "🏈 Gridiron Contender"

    # Featured badges handling
    unlocked_badges = sync_and_get_user_badges(user_id)
    valid_current_featured = [b for b in (profile.get("featured_badges", []) if isinstance(profile.get("featured_badges", []), list) else []) if b in unlocked_badges]

    # Target player showcase badges
    target_badges = sync_and_get_user_badges(target_player_id) if target_player_id == user_id else (target_player.get("unlocked_badges") or [])
    progress_ratio = len(target_badges) / len(MASTER_BADGES) if MASTER_BADGES else 0

    selected_team_data = NFL_TEAM_DATA.get(target_player.get("favorite_team"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"])

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "profile": profile,
        "target_player": target_player,
        "all_league_profiles": all_league_profiles,
        "nfl_teams": NFL_TEAMS,
        "nfl_team_data": NFL_TEAM_DATA,
        "avatar_options": AVATAR_OPTIONS,
        "border_style_options": BORDER_STYLE_OPTIONS,
        "unlocked_title_options": unlocked_title_options,
        "curr_selected_title": curr_selected_title,
        "locked_title_info": locked_title_info,
        "unlocked_badges": unlocked_badges,
        "valid_current_featured": valid_current_featured,
        "target_badges": target_badges,
        "master_badges": MASTER_BADGES,
        "progress_ratio": int(progress_ratio * 100),
        "target_team_logo": selected_team_data["logo"],
        "earned_title": get_earned_title(target_player_id),
        "msg": request.query_params.get("msg")
    })


@router.post("/update")
async def update_profile_settings(
    full_name: str = Form(...),
    favorite_team: str = Form(...),
    selected_title: str = Form(...),
    avatar_emoji: str = Form(...),
    avatar_border: str = Form(...),
    avatar_color: str = Form(...),
    favorite_player: Optional[str] = Form(""),
    bio: Optional[str] = Form("Ready for Kickoff!"),
    user_auth: dict = Depends(get_current_user)
):
    """Updates user profile customization settings matching app.py."""
    user_id = user_auth["id"]

    if not full_name.strip():
        raise HTTPException(status_code=400, detail="Display Name cannot be blank.")
    if contains_profanity(full_name) or contains_profanity(favorite_player or "") or contains_profanity(bio or ""):
        raise HTTPException(status_code=400, detail="Restricted language detected in profile inputs.")

    try:
        supabase.table("profiles").update({
            "full_name": full_name.strip(),
            "favorite_team": favorite_team,
            "selected_title": selected_title,
            "avatar_emoji": avatar_emoji,
            "avatar_border": avatar_border,
            "avatar_color": avatar_color,
            "favorite_player": (favorite_player or "").strip(),
            "bio": (bio or "Ready for Kickoff!").strip()
        }).eq("id", user_id).execute()

        return RedirectResponse(url="/profile?msg=Profile+Updated+Successfully", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating profile: {str(e)}")


@router.post("/featured-badges/save")
async def save_featured_badges(
    request: Request,
    user_auth: dict = Depends(get_current_user)
):
    """Saves the user's featured badge showcase selection (up to 3) matching app.py."""
    user_id = user_auth["id"]
    form_data = await request.form()
    
    # Extract list of selected badges from multi-select form keys
    selected_badges = form_data.getlist("featured_badges")
    if len(selected_badges) > 3:
        selected_badges = selected_badges[:3]

    try:
        supabase.table("profiles").update({
            "featured_badges": selected_badges
        }).eq("id", user_id).execute()

        return RedirectResponse(url="/profile?msg=Featured+Badges+Updated", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating featured badges: {str(e)}")
