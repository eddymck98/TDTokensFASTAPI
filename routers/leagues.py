import random
import string
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from utils.database import supabase
from utils.dependencies import get_current_user
from utils.helpers import NFL_TEAM_DATA, contains_profanity

router = APIRouter(prefix="/leagues", tags=["Leagues"])
templates = Jinja2Templates(directory="templates")

GLOBAL_LEAGUE_ID = "00000000-0000-0000-0000-000000000001"


def get_true_global_token_balance(target_user_id: str) -> int:
    """Retrieves the true global token balance matching app.py."""
    try:
        res = supabase.table("profiles").select("tokens").eq("id", target_user_id).single().execute()
        return max(0, (res.data or {}).get("tokens", 10))
    except Exception:
        return 10


def calculate_nemesis(target_user_id: str, allowed_peer_ids: Optional[set] = None):
    """Calculates user nemesis matching app.py logic."""
    try:
        user_bets = supabase.table("user_bets").select("week_number, question_id, pick").eq("user_id", target_user_id).execute().data
        if not user_bets:
            return "None Yet", 0
        user_picks_map = {(b["week_number"], b["question_id"]): b["pick"] for b in user_bets}
        rival_disagreements = {}

        for (w_num, q_id), u_pick in user_picks_map.items():
            other_bets_query = supabase.table("user_bets").select("user_id, pick, weekly_questions(winning_answer)").eq("week_number", w_num).eq("question_id", q_id).neq("user_id", target_user_id)
            if allowed_peer_ids is not None:
                if not allowed_peer_ids:
                    continue
                other_bets_query = other_bets_query.in_("user_id", list(allowed_peer_ids))
            other_bets = other_bets_query.execute().data
            if other_bets:
                for ob in other_bets:
                    rival_id, rival_pick, winning_ans = ob["user_id"], ob["pick"], ob.get("weekly_questions", {}).get("winning_answer")
                    if rival_pick != u_pick and winning_ans in ["Yes", "No"] and rival_pick == winning_ans:
                        rival_disagreements[rival_id] = rival_disagreements.get(rival_id, 0) + 1

        if not rival_disagreements:
            return "None Yet", 0
        nemesis_id = max(rival_disagreements, key=rival_disagreements.get)
        nemesis_prof = supabase.table("profiles").select("full_name").eq("id", nemesis_id).single().execute().data
        return nemesis_prof.get("full_name", "Unknown Rival") if nemesis_prof else "Unknown Rival", rival_disagreements[nemesis_id]
    except Exception:
        return "None Yet", 0


def calculate_streak(target_user_id: str) -> str:
    """Calculates current winning streak matching app.py."""
    try:
        u_bets = supabase.table("user_bets").select("week_number, pick, weekly_questions(winning_answer)").eq("user_id", target_user_id).order("week_number", desc=True).execute().data
        if not u_bets:
            return "0W"
        streak = 0
        for b in u_bets:
            w_ans = b.get("weekly_questions", {}).get("winning_answer")
            if w_ans in ["Yes", "No"]:
                if b["pick"] == w_ans:
                    streak += 1
                else:
                    break
        return f"{streak}W" if streak > 0 else "0W"
    except Exception:
        return "0W"


def get_leaderboard_stats(allowed_peer_ids: Optional[set] = None):
    """Calculates detailed statistics for leaderboard display matching app.py."""
    profiles_res = supabase.table("profiles").select("id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title, featured_badges, unlocked_badges, favorite_player, bio, default_league_view").execute().data
    if not profiles_res:
        return []
    
    stats = []
    for p in profiles_res:
        if allowed_peer_ids is not None and p["id"] not in allowed_peer_ids:
            continue
        true_global_tokens = get_true_global_token_balance(p["id"])
        correct_tds = supabase.table("touchdown_picks").select("*").eq("user_id", p["id"]).eq("is_correct", True).execute().data
        u_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", p["id"]).execute().data
        wins, total_graded = 0, 0
        for b in u_bets:
            w_ans = b.get("weekly_questions", {}).get("winning_answer")
            if w_ans in ["Yes", "No"]:
                total_graded += 1
                if b["pick"] == w_ans:
                    wins += 1
        nem_name, nem_score = calculate_nemesis(p["id"], allowed_peer_ids=allowed_peer_ids)
        stats.append({
            **p,
            "tokens": true_global_tokens,
            "correct_tds": len(correct_tds) if correct_tds else 0,
            "win_rate": int((wins / total_graded) * 100) if total_graded > 0 else 0,
            "total_bets": total_graded,
            "nemesis_name": nem_name,
            "nemesis_score": nem_score,
            "streak": calculate_streak(p["id"])
        })
    return sorted(stats, key=lambda x: (-x["tokens"], -x["correct_tds"], x["full_name"]))


@router.get("/", response_class=HTMLResponse)
async def view_leagues_page(
    request: Request,
    view_league_id: Optional[str] = None,
    user_auth: dict = Depends(get_current_user)
):
    """Renders the comprehensive Leagues Standings, Mini-Leagues, Chat Feed, and Archives tab matching app.py."""
    user_id = user_auth["id"]
    profile_res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = profile_res.data if profile_res and profile_res.data else {}

    # Fetch user memberships
    my_memberships = supabase.table("league_members").select("league_id, leagues(id, league_name, invite_code, created_by)").eq("user_id", user_id).execute().data
    all_my_leagues = [m for m in my_memberships if m.get("leagues")]

    league_filter_options = {}
    if next((m for m in all_my_leagues if m["leagues"]["id"] == GLOBAL_LEAGUE_ID), None):
        league_filter_options["🏆 Global Leaderboard"] = GLOBAL_LEAGUE_ID
    for m in [m for m in all_my_leagues if m["leagues"]["id"] != GLOBAL_LEAGUE_ID]:
        league_filter_options[f"🛡️ {m['leagues']['league_name']} (Mini-League)"] = m['leagues']['id']

    default_view_id = profile.get("default_league_view", GLOBAL_LEAGUE_ID)
    selected_league_id = view_league_id or (default_view_id if default_view_id in league_filter_options.values() else GLOBAL_LEAGUE_ID)

    is_global_view = (selected_league_id == GLOBAL_LEAGUE_ID)
    selected_league_info = next((m["leagues"] for m in all_my_leagues if m["leagues"]["id"] == selected_league_id), {"league_name": "Global Leaderboard"})
    clean_display_name = selected_league_info.get("league_name", "Global Standings")

    # Fetch leaderboard stats for selected view
    allowed_peer_ids = None if is_global_view else {cm["user_id"] for cm in supabase.table("league_members").select("user_id").eq("league_id", selected_league_id).execute().data or []}
    filtered_player_stats = get_leaderboard_stats(allowed_peer_ids=allowed_peer_ids)

    # Hall of Fame Archives
    archives_res = []
    try:
        archives_res = supabase.table("archived_seasons").select("season_label, standings_json, archived_at").eq("league_id", selected_league_id).order("archived_at", desc=True).execute().data or []
    except Exception:
        pass

    # Trash Talk Feed
    recent_chats = supabase.table("trash_talk").select("message, created_at, user_id").eq("league_id", selected_league_id).order("created_at", desc=True).limit(10).execute().data or []
    profiles_map = {p["id"]: p for p in supabase.table("profiles").select("*").execute().data or []}

    return templates.TemplateResponse("leagues.html", {
        "request": request,
        "profile": profile,
        "all_my_leagues": all_my_leagues,
        "league_filter_options": league_filter_options,
        "selected_league_id": selected_league_id,
        "is_global_view": is_global_view,
        "clean_display_name": clean_display_name,
        "filtered_player_stats": filtered_player_stats,
        "archives_res": archives_res,
        "recent_chats": recent_chats,
        "profiles_map": profiles_map,
        "nfl_team_data": NFL_TEAM_DATA,
        "msg": request.query_params.get("msg")
    })


@router.post("/create")
async def create_league(
    league_name: str = Form(...),
    league_password: Optional[str] = Form(""),
    user_auth: dict = Depends(get_current_user)
):
    """Creates a new custom mini-league matching app.py."""
    user_id = user_auth["id"]
    if not league_name.strip():
        raise HTTPException(status_code=400, detail="League name cannot be blank.")
    if contains_profanity(league_name):
        raise HTTPException(status_code=400, detail="League name contains restricted language.")

    invite_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    try:
        res_l = supabase.table("leagues").insert({
            "league_name": league_name.strip(),
            "invite_code": invite_code,
            "created_by": user_id,
            "league_password": league_password.strip() if league_password else ""
        }).execute()

        if res_l.data:
            new_league_id = res_l.data[0]["id"]
            supabase.table("league_members").insert({
                "league_id": new_league_id,
                "user_id": user_id
            }).execute()
            return RedirectResponse(url=f"/leagues?view_league_id={new_league_id}&msg=League+Created+Successfully", status_code=303)
        else:
            raise HTTPException(status_code=400, detail="Failed to create league.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating league: {str(e)}")


@router.post("/join")
async def join_league(
    invite_code: str = Form(...),
    league_password: Optional[str] = Form(""),
    user_auth: dict = Depends(get_current_user)
):
    """Allows users to join a custom mini-league via invite code matching app.py."""
    user_id = user_auth["id"]
    clean_code = invite_code.strip().upper()
    if not clean_code:
        raise HTTPException(status_code=400, detail="Please enter an invite code.")

    found_league = supabase.table("leagues").select("id, league_name, league_password").eq("invite_code", clean_code).execute().data
    if not found_league:
        raise HTTPException(status_code=400, detail="Invalid invite code. Please check with your commissioner.")

    target_league = found_league[0]
    if target_league.get("league_password", "") and target_league.get("league_password", "") != (league_password or "").strip():
        raise HTTPException(status_code=400, detail="Incorrect league password.")

    already_member = supabase.table("league_members").select("id").eq("league_id", target_league["id"]).eq("user_id", user_id).execute().data
    if already_member:
        raise HTTPException(status_code=400, detail=f"You are already a member of '{target_league['league_name']}'!")

    supabase.table("league_members").insert({
        "league_id": target_league["id"],
        "user_id": user_id
    }).execute()

    return RedirectResponse(url=f"/leagues?view_league_id={target_league['id']}&msg=Successfully+Joined+League", status_code=303)


@router.post("/chat/post")
async def post_trash_talk(
    league_id: str = Form(...),
    message: str = Form(...),
    user_auth: dict = Depends(get_current_user)
):
    """Posts messages to the mini-league trash talk feed matching app.py."""
    user_id = user_auth["id"]
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be blank.")
    if contains_profanity(message):
        raise HTTPException(status_code=400, detail="Message contains restricted language.")

    try:
        supabase.table("trash_talk").insert({
            "user_id": user_id,
            "message": message.strip(),
            "league_id": league_id
        }).execute()
        return RedirectResponse(url=f"/leagues?view_league_id={league_id}&msg=Message+Posted", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error posting message: {str(e)}")


@router.post("/default-view/save")
async def save_default_league_view(
    default_league_view: str = Form(...),
    user_auth: dict = Depends(get_current_user)
):
    """Saves the user's default standings view preference matching app.py."""
    user_id = user_auth["id"]
    supabase.table("profiles").update({"default_league_view": default_league_view}).eq("id", user_id).execute()
    return RedirectResponse(url=f"/leagues?view_league_id={default_league_view}&msg=Default+View+Updated", status_code=303)
