import os
import json
import re
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import Client

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
async def get_bets_page(request: Request, supabase: Client = Depends(get_supabase)):
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

    try:
        # Fetch profile by email to guarantee database match
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
            latest_week = available_weeks[-1]

            # Fetch existing user bets for latest week
            user_bets_res = supabase.table("user_bets").select("*").eq("user_id", user.id).eq("week_number", latest_week).execute()
            user_bets_map = {b["question_id"]: b for b in user_bets_res.data} if user_bets_res.data else {}

            # Fetch existing touchdown pick for latest week
            td_res = supabase.table("touchdown_picks").select("player_name").eq("user_id", user.id).eq("week_number", latest_week).execute()
            if td_res.data:
                touchdown_pick = td_res.data[0].get("player_name", "")

            # Fetch weekly question slate
            q_res = supabase.table("weekly_questions").select("id, question_number, question_text").eq("week_number", latest_week).lt("question_number", 11).order("question_number").execute()
            
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
                        "away_team": away_team,
                        "home_team": home_team,
                        "away_logo": extract_team_logo(away_team),
                        "home_logo": extract_team_logo(home_team),
                        "user_pick": existing_bet.get("pick", "Yes"),
                        "user_wager": existing_bet.get("wager_amount", 0)
                    })

    except Exception as e:
        print(f"Error loading bets page: {e}")

    return templates.TemplateResponse(
        request=request,
        name="bets.html",
        context={
            "request": request,
            "profile": profile,
            "active_tokens": profile.get("tokens", 10),
            "available_weeks": available_weeks,
            "questions": questions,
            "existing_touchdown_pick": touchdown_pick
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

        return RedirectResponse(url="/bets?success=bets_locked", status_code=303)
    except Exception as e:
        print(f"Bet Submission Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
