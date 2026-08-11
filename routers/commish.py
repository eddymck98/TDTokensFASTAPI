import json
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from supabase import Client
from database import NFL_TEAM_DATA

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_supabase(request: Request) -> Client:
    return request.app.state.supabase

@router.get("/", response_class=HTMLResponse)
async def commish_portal(request: Request, league_id: Optional[str] = None):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/auth/login", status_code=303)

    supabase = request.app.state.supabase
    try:
        token_data = json.loads(session_cookie)
        access_token = token_data.get("access_token")
        supabase.auth.set_session(access_token, token_data.get("refresh_token"))
        user = supabase.auth.get_user(access_token).user
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)

        profile_res = supabase.table("profiles").select("*").eq("email", user.email).execute()
        current_profile = profile_res.data[0] if profile_res.data else {}
    except Exception:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Fetch all leagues where the current user is an authorized commissioner (role = 'commissioner') or primary commissioner_id
    managed_leagues = []
    try:
        # Check membership table where role is commissioner
        member_res = supabase.table("league_members").select("league_id, role, leagues(*)").eq("user_id", current_profile["id"]).eq("role", "commissioner").execute()
        if member_res.data:
            for m in member_res.data:
                if m.get("leagues"):
                    managed_leagues.append(m["leagues"])
        
        # Fallback/merge legacy leagues where commissioner_id matches directly
        legacy_res = supabase.table("leagues").select("*").eq("commissioner_id", current_profile["id"]).execute()
        if legacy_res.data:
            existing_ids = {l["id"] for l in managed_leagues}
            for l in legacy_res.data:
                if l["id"] not in existing_ids:
                    managed_leagues.append(l)
    except Exception as e:
        print(f"Error fetching managed leagues: {e}")

    if not managed_leagues:
        return templates.TemplateResponse(request, name="commish.html", context={
            "request": request, 
            "profile": current_profile, 
            "managed_leagues": [], 
            "selected_league": None, 
            "league_members": [],
            "direct_challenge_link": "",
            "team_data": NFL_TEAM_DATA
        })

    # Select active league based on query param or default to the first one
    selected_league = next((l for l in managed_leagues if l["id"] == league_id), managed_leagues[0])

    # Build Direct Challenge Referral Link
    base_url = str(request.base_url).rstrip("/")
    invite_code = selected_league.get("invite_code", "SLATE")
    direct_challenge_link = f"{base_url}/leagues/join?code={invite_code}"

    # Fetch members of the selected league including roles
    league_members = []
    try:
        members_res = supabase.table("league_members").select("user_id, role, profiles(full_name, email, tokens)").eq("league_id", selected_league["id"]).execute()
        if members_res.data:
            for m in members_res.data:
                p_info = m.get("profiles") or {}
                league_members.append({
                    "user_id": m["user_id"],
                    "role": m.get("role", "member"),
                    "full_name": p_info.get("full_name", "Unknown"),
                    "email": p_info.get("email", ""),
                    "tokens": p_info.get("tokens", 10)
                })
    except Exception as e:
        print(f"Error fetching league members: {e}")

    return templates.TemplateResponse(
        request,
        name="commish.html",
        context={
            "request": request,
            "profile": current_profile,
            "managed_leagues": managed_leagues,
            "selected_league": selected_league,
            "direct_challenge_link": direct_challenge_link,
            "league_members": league_members,
            "team_data": NFL_TEAM_DATA
        }
    )

@router.post("/add-commissioner")
async def add_co_commissioner(
    request: Request,
    league_id: str = Form(...),
    member_user_id: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    """Promotes an existing league member to co-commissioner."""
    try:
        session_cookie = request.cookies.get("td_tokens_session")
        if session_cookie:
            token_data = json.loads(session_cookie)
            supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
            user = supabase.auth.get_user().user
            if user:
                # Verify request sender is commissioner
                league_check = supabase.table("leagues").select("commissioner_id").eq("id", league_id).execute()
                is_primary = league_check.data and league_check.data[0].get("commissioner_id") == user.id
                
                mem_check = supabase.table("league_members").select("role").eq("league_id", league_id).eq("user_id", user.id).execute()
                is_co_commish = mem_check.data and mem_check.data[0].get("role") == "commissioner"

                if not is_primary and not is_co_commish:
                    raise HTTPException(status_code=403, detail="Unauthorized action.")

        supabase.table("league_members").update({"role": "commissioner"}).eq("league_id", league_id).eq("user_id", member_user_id).execute()
        return RedirectResponse(url=f"/commish?league_id={league_id}&success=co_commish_added", status_code=303)
    except Exception as e:
        print(f"Error adding co-commissioner: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/announcement")
async def post_league_announcement(
    league_id: str = Form(...),
    announcement_text: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        # 1. Update league announcement text
        supabase.table("leagues").update({"announcement": announcement_text.strip()}).eq("id", league_id).execute()
        
        # 2. Automatically push commissioner announcement into the mini-league's Trash Talk feed
        league_res = supabase.table("leagues").select("commissioner_id").eq("id", league_id).single().execute()
        if league_res.data:
            commish_id = league_res.data.get("commissioner_id")
            if commish_id:
                supabase.table("trash_talk").insert({
                    "user_id": commish_id,
                    "league_id": league_id,
                    "message": f"📢 [COMMISSIONER ANNOUNCEMENT]: {announcement_text.strip()}"
                }).execute()

        return RedirectResponse(url=f"/commish?league_id={league_id}&success=announcement_posted", status_code=303)
    except Exception as e:
        print(f"Error posting announcement: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/update-settings")
async def update_league_settings(
    league_id: str = Form(...),
    league_name: str = Form(...),
    invite_code: str = Form(...),
    league_password: Optional[str] = Form(None),
    supabase: Client = Depends(get_supabase)
):
    try:
        update_data = {
            "name": league_name.strip(),
            "league_name": league_name.strip(),
            "invite_code": invite_code.strip().upper()
        }
        if league_password:
            update_data["league_password"] = league_password.strip()
        
        supabase.table("leagues").update(update_data).eq("id", league_id).execute()
        return RedirectResponse(url=f"/commish?league_id={league_id}&success=settings_updated", status_code=303)
    except Exception as e:
        print(f"Error updating league settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/kick-user")
async def kick_league_member(
    league_id: str = Form(...),
    user_id: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        supabase.table("league_members").delete().eq("league_id", league_id).eq("user_id", user_id).execute()
        return RedirectResponse(url=f"/commish?league_id={league_id}&success=user_kicked", status_code=303)
    except Exception as e:
        print(f"Error kicking user: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/transfer-ownership")
async def transfer_commissioner_ownership(
    league_id: str = Form(...),
    new_commissioner_id: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        # Update the league's commissioner_id to the new user and grant them commissioner role
        supabase.table("leagues").update({"commissioner_id": new_commissioner_id}).eq("id", league_id).execute()
        supabase.table("league_members").update({"role": "commissioner"}).eq("league_id", league_id).eq("user_id", new_commissioner_id).execute()
        return RedirectResponse(url="/commish?success=ownership_transferred", status_code=303)
    except Exception as e:
        print(f"Error transferring ownership: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/delete-league")
async def delete_league(
    request: Request,
    league_id: str = Form(...),
    confirmation_name: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        session_cookie = request.cookies.get("td_tokens_session")
        if not session_cookie:
            raise HTTPException(status_code=401, detail="Unauthorized session.")
        
        token_data = json.loads(session_cookie)
        supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
        user = supabase.auth.get_user().user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")

        # Fetch league details safely using select("*")
        league_res = supabase.table("leagues").select("*").eq("id", league_id).execute()
        if not league_res.data:
            raise HTTPException(status_code=404, detail="League not found.")
        
        league = league_res.data[0]
        
        # Check if user is primary commissioner or co-commissioner
        is_primary = league.get("commissioner_id") == user.id
        mem_check = supabase.table("league_members").select("role").eq("league_id", league_id).eq("user_id", user.id).execute()
        is_co_commish = mem_check.data and mem_check.data[0].get("role") == "commissioner"

        if not is_primary and not is_co_commish:
            raise HTTPException(status_code=403, detail="Only league commissioners can delete this league.")

        actual_name = league.get("name") or league.get("league_name") or ""
        if confirmation_name.strip() != actual_name.strip():
            return RedirectResponse(url=f"/commish?league_id={league_id}&error=name_mismatch", status_code=303)

        # Execute league deletion
        supabase.table("leagues").delete().eq("id", league_id).execute()

        return RedirectResponse(url="/leagues/?success=league_deleted", status_code=303)
    except Exception as e:
        print(f"Error deleting league: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/archive-season")
async def archive_league_season(
    request: Request,
    league_id: str = Form(...),
    season_label: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        session_cookie = request.cookies.get("td_tokens_session")
        if session_cookie:
            token_data = json.loads(session_cookie)
            supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
            user = supabase.auth.get_user().user
            if user:
                league_check = supabase.table("leagues").select("commissioner_id").eq("id", league_id).execute()
                is_primary = league_check.data and league_check.data[0].get("commissioner_id") == user.id
                
                mem_check = supabase.table("league_members").select("role").eq("league_id", league_id).eq("user_id", user.id).execute()
                is_co_commish = mem_check.data and mem_check.data[0].get("role") == "commissioner"

                if not is_primary and not is_co_commish:
                    raise HTTPException(status_code=403, detail="Only league commissioners can archive seasons.")

        members_res = supabase.table("league_members").select("user_id, profiles(id, full_name, tokens)").eq("league_id", league_id).execute()
        
        td_res = supabase.table("touchdown_picks").select("user_id, is_correct").eq("is_correct", True).execute()
        td_counts = {}
        if td_res.data:
            for td in td_res.data:
                uid = td["user_id"]
                td_counts[uid] = td_counts.get(uid, 0) + 1

        rows = []
        if members_res.data:
            for m in members_res.data:
                p = m.get("profiles")
                if p:
                    uid = p["id"]
                    rows.append({
                        "user_id": uid,
                        "full_name": p.get("full_name") or "Unknown",
                        "tokens": p.get("tokens", 10),
                        "correct_tds": td_counts.get(uid, 0)
                    })

        rows = sorted(rows, key=lambda x: (x["tokens"], x["correct_tds"]), reverse=True)
        
        snapshot = []
        current_rank = 1
        for i, row in enumerate(rows):
            if i > 0:
                prev = rows[i - 1]
                if row["tokens"] != prev["tokens"] or row["correct_tds"] != prev["correct_tds"]:
                    current_rank = i + 1
            
            rank_display = f"🥇" if current_rank == 1 else (f"🥈" if current_rank == 2 else (f"🥉" if current_rank == 3 else f"#{current_rank}"))
            
            snapshot.append({
                "Rank": rank_display,
                "full_name": row["full_name"],
                "tokens": row["tokens"]
            })

        supabase.table("archived_seasons").insert({
            "league_id": league_id,
            "season_label": season_label.strip(),
            "standings_json": snapshot
        }).execute()

        return RedirectResponse(url=f"/commish?league_id={league_id}&success=season_archived", status_code=303)
    except Exception as e:
        print(f"Error archiving season: {e}")
        raise HTTPException(status_code=400, detail=str(e))
