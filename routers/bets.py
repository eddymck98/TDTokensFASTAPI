import os
import json
import re
from typing import Optional
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import Client

# Import NFL_TEAM_DATA from your database module to satisfy base.html requirements
from database import NFL_TEAM_DATA

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_supabase(request: Request) -> Client:
    return request.app.state.supabase

# High-resolution NFL Team Logo Dictionary
TEAM_LOGOS = {
    "Arizona Cardinals": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png",
    "Atlanta Falcons": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png",
    "Baltimore Ravens": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png",
    "Buffalo Bills": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
    "Carolina Panthers": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png",
    "Chicago Bears": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png",
    "Cincinnati Bengals": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png",
    "Cleveland Browns": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png",
    "Dallas Cowboys": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
    "Denver Broncos": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png",
    "Detroit Lions": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png",
    "Green Bay Packers": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png",
    "Houston Texans": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png",
    "Indianapolis Colts": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png",
    "Jacksonville Jaguars": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png",
    "Kansas City Chiefs": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
    "Las Vegas Raiders": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png",
    "Los Angeles Chargers": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png",
    "Los Angeles Rams": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png",
    "Miami Dolphins": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png",
    "Minnesota Vikings": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png",
    "New England Patriots": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png",
    "New Orleans Saints": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png",
    "New York Giants": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png",
    "New York Jets": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png",
    "Philadelphia Eagles": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
    "Pittsburgh Steelers": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png",
    "San Francisco 49ers": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
    "Seattle Seahawks": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png",
    "Tampa Bay Buccaneers": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png",
    "Tennessee Titans": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png",
    "Washington Commanders": "https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png",
}

DEFAULT_LOGO = "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true"

def extract_team_logo(team_str: str) -> str:
    """Helper to strip emojis and match team name to logo URL."""
    clean_name = re.sub(r'[^\w\s]', '', team_str).strip()
    return TEAM_LOGOS.get(clean_name, DEFAULT_LOGO)

@router.get("/", response_class=HTMLResponse)
async def get_bets_page(request: Request, week: Optional[int] = None, supabase: Client = Depends(get_supabase)):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        ref_token = token_data.get("refresh_token")
        supabase.auth.set_session(acc_token, ref_token)
        user = supabase.auth.get_user(acc_token).user
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)
    except Exception:
        return RedirectResponse(url="/auth/login", status_code=303)

    available_weeks = []
    profile = {}
    questions = []
    touchdown_pick = ""
    lockout_time = ""
    target_week = 1
    is_week_closed = False
    is_published = True
    user_td_won = False
    official_td_winner = "Pending"

    try:
        # Fetch profile by email
        profile_res = supabase.table("profiles").select("*").eq("email", user.email).execute()
        profile = profile_res.data[0] if profile_res.data else {
            "tokens": 10,
            "full_name": user.email.split('@')[0],
            "favorite_team": "🏈 Free Agent / Neutral"
        }

        # Fetch active weeks
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else []
        
        if available_weeks:
            # Determine target week (default to requested or newest)
            target_week = week if week and week in available_weeks else available_weeks[-1]

            # Check if this specific week is published in a 'weeks' table or status row if available
            try:
                week_meta_res = supabase.table("weeks").select("is_published").eq("week_number", target_week).execute()
                if week_meta_res.data:
                    is_published = week_meta_res.data[0].get("is_published", True)
            except Exception:
                pass

            # Check if this specific week is closed by admin
            try:
                status_res = (
                    supabase.table("weekly_questions")
                    .select("winning_answer")
                    .eq("week_number", target_week)
                    .eq("question_number", 98)
                    .execute()
                )
                if status_res.data and status_res.data[0].get("winning_answer") == "CLOSED":
                    is_week_closed = True
            except Exception:
                pass

            # Fetch Admin Lockout Time for target week
            try:
                lockout_res = (
                    supabase.table("weekly_questions")
                    .select("winning_answer")
                    .eq("week_number", target_week)
                    .eq("question_number", 99)
                    .execute()
                )
                if lockout_res.data:
                    ans = lockout_res.data[0].get("winning_answer", "")
                    if ans.startswith("LOCKTIME:"):
                        lockout_time = ans.replace("LOCKTIME:", "")
            except Exception as e:
                print(f"Error fetching lockout time: {e}")

            # Fetch existing user bets for target week
            user_bets_res = supabase.table("user_bets").select("*").eq("user_id", user.id).eq("week_number", target_week).execute()
            user_bets_map = {b["question_id"]: b for b in user_bets_res.data} if user_bets_res.data else {}

            # Fetch existing touchdown pick for target week & grading status
            td_res = supabase.table("touchdown_picks").select("player_name, is_correct").eq("user_id", user.id).eq("week_number", target_week).execute()
            if td_res.data:
                touchdown_pick = td_res.data[0].get("player_name", "")
                is_correct_val = td_res.data[0].get("is_correct")
                if is_correct_val is not None:
                    user_td_won = bool(is_correct_val)

            # Fetch official touchdown scorer winning answer if stored in weekly_questions (e.g. question_number == 97)
            try:
                td_winner_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", target_week).eq("question_number", 97).execute()
                if td_winner_res.data:
                    official_td_winner = td_winner_res.data[0].get("winning_answer", "Pending")
            except Exception:
                pass

            # Fetch weekly question slate for target week
            q_res = supabase.table("weekly_questions").select("id, question_number, question_text, winning_answer").eq("week_number", target_week).lt("question_number", 11).order("question_number").execute()
            
            if q_res.data:
                for q in q_res.data:
                    q_id = q["id"]
                    raw_text = q.get("question_text", "")
                    
                    prompt = raw_text
                    away_team = "🏈 Free Agent / Neutral"
                    home_team = "🏈 Free Agent / Neutral"
                    
                    if " | MATCHUP: " in raw_text:
                        parts = raw_text.split(" | MATCHUP: ")
                        prompt = parts[0]
                        teams = parts[1].split(" @ ")
                        if len(teams) == 2:
                            away_team = teams[0]
                            home_team = teams[1]

                    existing_bet = user_bets_map.get(q_id, {})

                    questions.append({
                        "id": q_id,
                        "question_number": q.get("question_number", "?"),
                        "prompt": prompt,
                        "winning_answer": q.get("winning_answer", "Pending"),
                        "away_team": away_team,
                        "home_team": home_team,
                        "away_logo": extract_team_logo(away_team),
                        "home_logo": extract_team_logo(home_team),
                        "user_pick": existing_bet.get("pick", "Yes"),
                        "user_wager": existing_bet.get("wager_amount", 0)
                    })

    except Exception as e:
        print(f"Error loading bets data: {e}")

    # Pass request as positional arg & pass team_data into context for Base.html
    return templates.TemplateResponse(
        request,
        name="bets.html",
        context={
            "request": request,
            "profile": profile,
            "active_tokens": profile.get("tokens", 10),
            "available_weeks": available_weeks,
            "target_week": target_week,
            "is_week_closed": is_week_closed,
            "is_published": is_published,
            "questions": questions,
            "existing_touchdown_pick": touchdown_pick,
            "user_td_won": user_td_won,
            "official_td_winner": official_td_winner,
            "lockout_time": lockout_time,
            "team_data": NFL_TEAM_DATA
        }
    )

@router.post("/submit")
async def submit_weekly_bets(
    request: Request,
    week_number: int = Form(...),
    touchdown_pick: str = Form(""),
    supabase: Client = Depends(get_supabase)
):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    
    try:
        token_data = json.loads(session_cookie)
        supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
        user = supabase.auth.get_user(token_data.get("access_token")).user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # --- Check if this week has been closed/graded by the admin ---
    try:
        status_res = (
            supabase.table("weekly_questions")
            .select("winning_answer")
            .eq("week_number", week_number)
            .eq("question_number", 98)
            .execute()
        )
        if status_res.data:
            if status_res.data[0].get("winning_answer") == "CLOSED":
                raise HTTPException(status_code=400, detail="This week is closed. Bets can no longer be modified.")
    except HTTPException as he:
        raise he
    except Exception:
        pass
    # -------------------------------------------------------------

    form_data = await request.form()
    
    try:
        profile_res = supabase.table("profiles").select("full_name, tokens").eq("email", user.email).execute()
        profile = profile_res.data[0] if profile_res.data else {"full_name": "Player", "tokens": 10}

        # Clear existing bets for this week
        supabase.table("user_bets").delete().eq("user_id", user.id).eq("week_number", week_number).execute()
        
        total_wagered = 0
        bets_to_insert = []

        for key, value in form_data.items():
            if key.startswith("pick_"):
                q_id_str = key.replace("pick_", "")
                pick_val = value
                wager_val = int(form_data.get(f"wager_{q_id_str}", 0))
                total_wagered += wager_val

                try:
                    parsed_q_id = int(q_id_str)
                except ValueError:
                    parsed_q_id = q_id_str

                bets_to_insert.append({
                    "user_id": user.id,
                    "user_name": profile.get("full_name", "Player"),
                    "week_number": week_number,
                    "question_id": parsed_q_id,
                    "pick": pick_val,
                    "wager_amount": wager_val
                })

        if total_wagered > profile.get("tokens", 10):
            raise HTTPException(status_code=400, detail="Token allocation exceeds available balance.")

        for bet in bets_to_insert:
            supabase.table("user_bets").insert(bet).execute()

        # Update Touchdown Bonus Pick
        if touchdown_pick.strip():
            supabase.table("touchdown_picks").delete().eq("user_id", user.id).eq("week_number", week_number).execute()
            supabase.table("touchdown_picks").insert({
                "user_id": user.id,
                "week_number": week_number,
                "player_name": touchdown_pick.strip(),
                "is_correct": None
            }).execute()

        return RedirectResponse(url=f"/bets?week={week_number}&success=bets_locked", status_code=303)
    except Exception as e:
        print(f"Bet Submission Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
