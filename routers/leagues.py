import os
import json
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from supabase import Client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_supabase(request: Request) -> Client:
    return request.app.state.supabase

@router.get("/", response_class=HTMLResponse)
async def get_leagues_page(request: Request, league_id: Optional[str] = None, supabase: Client = Depends(get_supabase)):
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

    profile = {}
    user_leagues = []
    ranked_leaderboard = []
    selected_league = None
    is_global = True
    trash_talk_messages = []
    archived_seasons = []

    GLOBAL_LEAGUE_ID = "00000000-0000-0000-0000-000000000001"

    try:
        prof_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
        if prof_res.data:
            profile = prof_res.data[0]

        # If no league_id requested in query, check user's default saved preference
        if not league_id:
            league_id = profile.get("default_league_id", "global")

        memberships = supabase.table("league_members").select("league_id, leagues(*)").eq("user_id", user.id).execute()
        if memberships.data:
            for m in memberships.data:
                l_data = m.get("leagues")
                if l_data:
                    l_id = l_data.get("id")
                    l_name = l_data.get("name") or l_data.get("league_name") or ""
                    # Filter out duplicate global entries from mini-leagues list
                    if l_id == GLOBAL_LEAGUE_ID or l_name.lower() == "global leaderboard":
                        continue
                    l_data["name"] = l_name
                    user_leagues.append(l_data)

        is_global = (not league_id or league_id == "global" or league_id == GLOBAL_LEAGUE_ID)

        if not is_global:
            selected_league = next((l for l in user_leagues if l["id"] == league_id), None)
            if not selected_league:
                is_global = True

        td_res = supabase.table("touchdown_picks").select("user_id, is_correct").eq("is_correct", True).execute()
        td_counts = {}
        if td_res.data:
            for td in td_res.data:
                uid = td["user_id"]
                td_counts[uid] = td_counts.get(uid, 0) + 1

        leaderboard_rows = []

        if is_global:
            profiles_res = supabase.table("profiles").select("id, full_name, tokens, favorite_team, favorite_player, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title").execute()
            raw_profiles = profiles_res.data if profiles_res.data else []
            for p in raw_profiles:
                uid = p["id"]
                leaderboard_rows.append({
                    "user_id": uid,
                    "full_name": p.get("full_name") or "Unknown",
                    "tokens": p.get("tokens", 10),
                    "favorite_team": p.get("favorite_team", "Free Agent"),
                    "favorite_player": p.get("favorite_player", ""),
                    "avatar_emoji": p.get("avatar_emoji", "🏈"),
                    "avatar_border": p.get("avatar_border", "default"),
                    "avatar_color": p.get("avatar_color", "#1e3a8a"),
                    "selected_title": p.get("selected_title", ""),
                    "correct_tds": td_counts.get(uid, 0)
                })
        else:
            members_res = supabase.table("league_members").select("user_id, profiles(id, full_name, tokens, favorite_team, favorite_player, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title)").eq("league_id", selected_league["id"]).execute()
            if members_res.data:
                for m in members_res.data:
                    p = m.get("profiles")
                    if p:
                        uid = p["id"]
                        leaderboard_rows.append({
                            "user_id": uid,
                            "full_name": p.get("full_name") or "Unknown",
                            "tokens": p.get("tokens", 10),
                            "favorite_team": p.get("favorite_team", "Free Agent"),
                            "favorite_player": p.get("favorite_player", ""),
                            "avatar_emoji": p.get("avatar_emoji", "🏈"),
                            "avatar_border": p.get("avatar_border", "default"),
                            "avatar_color": p.get("avatar_color", "#1e3a8a"),
                            "selected_title": p.get("selected_title", ""),
                            "correct_tds": td_counts.get(uid, 0)
                        })

        leaderboard_rows = sorted(leaderboard_rows, key=lambda x: (x["tokens"], x["correct_tds"]), reverse=True)

        current_rank = 1
        for i, row in enumerate(leaderboard_rows):
            if i > 0:
                prev = leaderboard_rows[i - 1]
                if row["tokens"] != prev["tokens"] or row["correct_tds"] != prev["correct_tds"]:
                    current_rank = i + 1
            row["rank"] = current_rank
            ranked_leaderboard.append(row)

        # Apply Top 10 + User Fallback rule ONLY for Global Leaderboard
        displayed_leaderboard = ranked_leaderboard
        if is_global:
            top_ten = ranked_leaderboard[:10]
            user_in_top_ten = any(r["user_id"] == user.id for r in top_ten)
            if not user_in_top_ten:
                user_row = next((r for r in ranked_leaderboard if r["user_id"] == user.id), None)
                if user_row:
                    top_ten.append("SEPARATOR")
                    top_ten.append(user_row)
            displayed_leaderboard = top_ten

        chat_filter_id = GLOBAL_LEAGUE_ID if is_global else selected_league["id"]
        chat_res = supabase.table("trash_talk").select("*, profiles!trash_talk_user_id_fkey(full_name, avatar_emoji)").eq("league_id", chat_filter_id).order("created_at", desc=True).limit(20).execute()
        trash_talk_messages = chat_res.data if chat_res.data else []

        # Fetch Hall of Fame Archives for the selected mini-league
        if not is_global and selected_league:
            archive_res = supabase.table("archived_seasons").select("*").eq("league_id", selected_league["id"]).order("archived_at", desc=True).execute()
            archived_seasons = archive_res.data if archive_res.data else []

    except Exception as e:
        print(f"Leagues page error: {e}")

    return templates.TemplateResponse(request=request, name="leagues.html", context={
        "request": request,
        "user": user,
        "profile": profile,
        "user_leagues": user_leagues,
        "selected_league": selected_league,
        "is_global": is_global,
        "leaderboard": displayed_leaderboard,
        "trash_talk_messages": trash_talk_messages,
        "archived_seasons": archived_seasons,
        "active_league_id": league_id or "global"
    })

@router.post("/set-default")
async def set_default_league(
    request: Request,
    default_league_id: str = Form(...),
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
        
        supabase.table("profiles").update({"default_league_id": default_league_id}).eq("id", user.id).execute()
        return RedirectResponse(url=f"/leagues?league_id={default_league_id}&success=default_updated", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
            "name": league_name.strip(),
            "invite_code": invite_code,
            "created_by": user.id,
            "commissioner_id": user.id,
            "league_password": league_password.strip() if league_password else ""
        }).execute()
        
        if res_l.data:
            new_league_id = res_l.data[0]["id"]
            supabase.table("league_members").insert({
                "league_id": new_league_id,
                "user_id": user.id
            }).execute()

        return RedirectResponse(url=f"/leagues?league_id={new_league_id}&success=league_created", status_code=303)
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
        return RedirectResponse(url="/leagues?error=blank_code", status_code=303)

    try:
        found_league = supabase.table("leagues").select("id, league_name, name, league_password").eq("invite_code", clean_code).execute().data
        if not found_league:
            return RedirectResponse(url="/leagues?error=invalid_code", status_code=303)

        target_league = found_league[0]
        if target_league.get("league_password", "") and target_league.get("league_password", "") != league_password.strip():
            return RedirectResponse(url=f"/leagues?league_id={target_league['id']}&error=incorrect_password", status_code=303)

        already_member = supabase.table("league_members").select("id").eq("league_id", target_league["id"]).eq("user_id", user.id).execute().data
        if already_member:
            return RedirectResponse(url=f"/leagues?league_id={target_league['id']}&info=already_member", status_code=303)

        supabase.table("league_members").insert({
            "league_id": target_league["id"],
            "user_id": user.id
        }).execute()

        return RedirectResponse(url=f"/leagues?league_id={target_league['id']}&success=joined_league", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/leagues?error=server_error", status_code=303)

@router.post("/announcement")
async def post_mini_league_announcement(
    request: Request,
    league_id: str = Form(...),
    announcement_text: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    try:
        supabase.table("leagues").update({"announcement": announcement_text.strip()}).eq("id", league_id).execute()
        return RedirectResponse(url=f"/leagues?league_id={league_id}&success=announcement_posted", status_code=303)
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

        redirect_param = f"league_id={league_id}" if league_id != "00000000-0000-0000-0000-000000000001" else "league_id=global"
        return RedirectResponse(url=f"/leagues?{redirect_param}&success=message_posted", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/archive-season")
async def archive_season(
    request: Request,
    league_id: str = Form(...),
    season_label: str = Form(...),
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

        # Verify commissioner authorization
        league_check = supabase.table("leagues").select("commissioner_id").eq("id", league_id).execute()
        if not league_check.data or league_check.data[0].get("commissioner_id") != user.id:
            raise HTTPException(status_code=403, detail="Only the league commissioner can archive seasons.")

        # Fetch current standings for this mini league to build the snapshot JSON
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
            
            # Format rank with emoji badge for top 3
            rank_display = f"🥇" if current_rank == 1 else (f"🥈" if current_rank == 2 else (f"🥉" if current_rank == 3 else f"#{current_rank}"))
            
            snapshot.append({
                "Rank": rank_display,
                "full_name": row["full_name"],
                "tokens": row["tokens"]
            })

        # Insert into archived_seasons table
        supabase.table("archived_seasons").insert({
            "league_id": league_id,
            "season_label": season_label.strip(),
            "standings_json": snapshot
        }).execute()

        return RedirectResponse(url=f"/leagues?league_id={league_id}&success=season_archived", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
