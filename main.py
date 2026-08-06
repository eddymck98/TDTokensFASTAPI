import os
import json
import random
from datetime import datetime, timezone
import pandas as pd
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from supabase import Client, create_client
import resend

# ==========================================
# 1. APP INITIALIZATION & CONFIGURATION
# ==========================================
app = FastAPI(title="Touchdown Tokens API")
templates = Jinja2Templates(directory="templates")

# Mount static files (for your CSS and images if hosted locally)
# app.mount("/static", StaticFiles(directory="static"), name="static")

resend.api_key = os.environ.get("RESEND_API_KEY", "")

def get_supabase() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")
    return create_client(supabase_url, supabase_key)

# ==========================================
# 2. CONSTANTS & STATIC DATA[cite: 3]
# ==========================================
PROFANITY_FILTER = ["damn", "hell", "crap", "shit", "fuck", "bitch", "asshole", "dick", "cunt", "bastard"][cite: 3]
DEFAULT_QUESTION_TEMPLATES = [
    "Will QB 1 throw for over 250+ passing yards?", "Will RB 1 rush for 75+ rushing yards?", 
    "Will WR 1 catch 6 or more receptions?", "Will Away Team score a touchdown in the 1st quarter?", 
    "Will there be a successful 50+ yard Field Goal kicked?", "Will this game have over 45.5 combined points scored?", 
    "Will any Defense record a pick-six or fumble recovery touchdown?", "Will TE 1 score a rushing or receiving touchdown?", 
    "Will this game go into Overtime?", "Will Home Team record 3 or more sacks?"
][cite: 3]

NFL_TEAM_DATA = {
    "🏈 Free Agent / Neutral": {"logo": "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true", "color": "#fbbf24", "stadium": "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"},
    "🔴 Arizona Cardinals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png", "color": "#97233F"},
    "🔴 Atlanta Falcons": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png", "color": "#A71930"},
    "🟣 Baltimore Ravens": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png", "color": "#241773"},
    "🔴 Buffalo Bills": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png", "color": "#00338D"},
    "🔵 Carolina Panthers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png", "color": "#0085CA"},
    "🟠 Chicago Bears": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png", "color": "#C83803"},
    "🟠 Cincinnati Bengals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png", "color": "#FB4F14"},
    "🟤 Cleveland Browns": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png", "color": "#FF3C00"},
    "🔵 Dallas Cowboys": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png", "color": "#003594"},
    "🟠 Denver Broncos": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png", "color": "#FB4F14"},
    "🔵 Detroit Lions": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png", "color": "#0076B6"},
    "🟢 Green Bay Packers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png", "color": "#203731"},
    "🔴 Houston Texans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png", "color": "#03202F"},
    "🔵 Indianapolis Colts": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png", "color": "#002C5F"},
    "🐆 Jacksonville Jaguars": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png", "color": "#006778"},
    "🔴 Kansas City Chiefs": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png", "color": "#E31837"},
    "🪙 Las Vegas Raiders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png", "color": "#A5ACAF"},
    "⚡ Los Angeles Chargers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png", "color": "#0080C6"},
    "🟡 Los Angeles Rams": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png", "color": "#003594"},
    "🐬 Miami Dolphins": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png", "color": "#008E97"},
    "🟣 Minnesota Vikings": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png", "color": "#4F2683"},
    "🔵 New England Patriots": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png", "color": "#002244"},
    "⚜️ New Orleans Saints": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png", "color": "#D3BC8D"},
    "🔵 New York Giants": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png", "color": "#0B2265"},
    "🟢 New York Jets": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png", "color": "#125740"},
    "🦅 Philadelphia Eagles": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png", "color": "#004C54"},
    "🟡 Pittsburgh Steelers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png", "color": "#FFB612"},
    "🔴 San Francisco 49ers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png", "color": "#AA0000"},
    "🟢 Seattle Seahawks": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png", "color": "#69BE28"},
    "🔴 Tampa Bay Buccaneers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png", "color": "#D50A0A"},
    "🔵 Tennessee Titans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png", "color": "#4B92DB"},
    "🔴 Washington Commanders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/was.png", "color": "#5A1414"},
}[cite: 3]

MASTER_BADGES = {
    "🚀 Token Tycoon": "Accumulate 50+ lifetime tokens earned across your career", 
    "🎯 High Roller": "Wager 10+ tokens on a single question",
    "⚡ Double Down Legend": "Wager 15+ total tokens in a single week",
    "💣 All-In Maverick": "Wager 100% of your remaining token balance on a slate",
    "🏈 TD Guru": "Correctly predict 5+ Touchdown Scorers",
    "📉 Down Bad": "Reach a token balance of 0 tokens",
    "🏆 League Champion": "Be crowned the official end-of-season League Champion",
    "⭐ League Commissioner": "Create or administer a custom mini-league"
}[cite: 3]

# ==========================================
# 3. HELPER FUNCTIONS[cite: 3]
# ==========================================
def contains_profanity(text: str) -> bool:
    if not text: return False
    text_lower = text.lower()
    words = text_lower.split()
    for p_word in PROFANITY_FILTER:
        if p_word in text_lower or any(p_word == w for w in words): return True
    return False[cite: 3]

def get_current_user(request: Request):
    """Dependency to extract user from Supabase JWT stored in cookies."""
    token = request.cookies.get("td_tokens_session")
    if not token:
        return None
    try:
        supabase = get_supabase()
        token_data = json.loads(token)
        res = supabase.auth.get_user(token_data.get("access_token"))
        return res.user
    except Exception:
        return None

def get_true_global_token_balance(target_user_id, supabase: Client):
    try: 
        data = supabase.table("profiles").select("tokens").eq("id", target_user_id).single().execute().data
        return max(0, data.get("tokens", 10)) if data else 10
    except Exception: 
        return 10[cite: 3]

def recalculate_all_user_balances(supabase_client: Client):
    try:
        all_profiles = supabase_client.table("profiles").select("id").execute().data
        if not all_profiles: return
        for prof in all_profiles:
            uid = prof["id"]
            u_bets = supabase_client.table("user_bets").select("week_number, wager_amount, pick, weekly_questions(winning_answer)").eq("user_id", uid).execute().data
            u_td = supabase_client.table("touchdown_picks").select("week_number, is_correct").eq("user_id", uid).eq("is_correct", True).execute().data
            td_wins_map = {td["week_number"]: 5 for td in u_td}
            curr_tokens = 10
            if u_bets or td_wins_map:
                for w in sorted(list(set([b["week_number"] for b in u_bets] + list(td_wins_map.keys())))):
                    for b in [b for b in u_bets if b["week_number"] == w]:
                        w_ans = b.get("weekly_questions", {}).get("winning_answer")
                        if w_ans in ["Yes", "No"]: 
                            curr_tokens += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
                    if w in td_wins_map: curr_tokens += 5
            supabase_client.table("profiles").update({"tokens": max(0, curr_tokens)}).eq("id", uid).execute()
    except Exception: 
        pass[cite: 3]

# ==========================================
# 4. VIEW ROUTERS (HTML Templates)
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def home_view(request: Request):
    """Renders the main portal or redirects to login."""
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
    
    supabase = get_supabase()
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
    tokens = get_true_global_token_balance(user.id, supabase)
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "profile": profile,
        "tokens": tokens,
        "nfl_teams": NFL_TEAM_DATA
    })

# ==========================================
# 5. AUTHENTICATION API ENDPOINTS
# ==========================================
@app.post("/auth/login")
async def login(email: str = Form(...), password: str = Form(...)):
    supabase = get_supabase()
    try:
        auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if auth_response.user and auth_response.user.email_confirmed_at:
            # Create response and set HTTPOnly cookie[cite: 3]
            response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
            token_data = json.dumps({
                "access_token": auth_response.session.access_token, 
                "refresh_token": auth_response.session.refresh_token
            })
            response.set_cookie(key="td_tokens_session", value=token_data, max_age=2592000, httponly=True)
            return response
        else:
            supabase.auth.sign_out()
            raise HTTPException(status_code=401, detail="Please authorise your email first.")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid login credentials.")[cite: 3]

@app.post("/auth/signup")
async def signup(
    first_name: str = Form(...), 
    surname: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...)
):
    supabase = get_supabase()
    combined_name = f"{first_name.strip()} {surname.strip()}"
    
    if contains_profanity(combined_name):
        raise HTTPException(status_code=400, detail="Name contains restricted language.")[cite: 3]
        
    try:
        # Check system locks[cite: 3]
        is_signup_locked = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 997).execute().data
        if is_signup_locked and is_signup_locked[0]["winning_answer"] == "LOCKED":
            raise HTTPException(status_code=403, detail="Sign-ups are temporarily locked by Admin.")[cite: 3]

        response = supabase.auth.sign_up({"email": email.strip(), "password": password})
        if response.user:
            new_uid = response.user.id
            supabase.table("profiles").insert({
                "id": new_uid, "email": email.strip(), "full_name": combined_name, 
                "tokens": 10, "is_admin": False, "favorite_team": "🏈 Free Agent / Neutral", 
                "selected_title": "🏈 Gridiron Contender", "default_league_view": "00000000-0000-0000-0000-000000000001"
            }).execute()[cite: 3]
            
            # Send Email via Resend[cite: 3]
            html_content = f"""<div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;"><div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);"><div style="text-align: center; margin-bottom: 30px;"><img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" style="width: 180px; margin-bottom: 15px; filter: drop-shadow(0px 6px 15px rgba(251, 191, 36, 0.4));" /><h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1><p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Weekly NFL Predictions & Wagers</p></div><h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3><p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">Thanks for registering an account with Touchdown Tokens. To lock in your weekly picks, compete on leaderboards, and claim your tokens, please authorise your email address below:</p><div style="text-align: center; margin: 35px 0;"><a href="https://tdtokens.co.uk" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">AUTHORISE EMAIL ADDRESS</a></div><p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">If you did not request this account creation or verification, you can safely ignore and delete this email.</p></div><div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">&copy; 2026 Touchdown Tokens. All rights reserved.</div></div>"""[cite: 3]
            resend.Emails.send({"from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>", "to": [email.strip()], "subject": "🏈 Authorise Your Touchdown Tokens Account", "html": html_content})[cite: 3]
            
            return JSONResponse(content={"message": "Account created. Please check your email to verify."})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("td_tokens_session")
    return response[cite: 3]

# ==========================================
# 6. BETTING & GAMEPLAY ENDPOINTS
# ==========================================
@app.post("/api/bets/submit")
async def submit_bets(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    data = await request.json()
    week_number = data.get("week_number")
    picks = data.get("picks") # Dict of {question_id: pick_value}
    wagers = data.get("wagers") # Dict of {question_id: wager_amount}
    td_pick = data.get("td_pick")
    
    supabase = get_supabase()
    
    # 1. Check Lockout[cite: 3]
    lock_time_row = supabase.table("weekly_questions").select("winning_answer").eq("week_number", week_number).ilike("winning_answer", "LOCKTIME:%").execute().data
    if lock_time_row:
        lock_dt = datetime.fromisoformat(lock_time_row[0]["winning_answer"].replace("LOCKTIME:", "")).replace(tzinfo=timezone.utc)
        if (lock_dt - datetime.now(timezone.utc)).total_seconds() <= 0:
            raise HTTPException(status_code=403, detail="Entries are locked! Kickoff deadline has passed.")[cite: 3]

    # 2. Validate Tokens[cite: 3]
    true_balance = get_true_global_token_balance(user.id, supabase)
    total_wagered = sum(int(amount) for amount in wagers.values())
    if total_wagered > true_balance:
        raise HTTPException(status_code=400, detail=f"Over-wagered. You only have {true_balance} tokens available.")[cite: 3]

    # 3. Profanity Check for TD Pick[cite: 3]
    if contains_profanity(td_pick):
        raise HTTPException(status_code=400, detail="Touchdown Scorer name contains restricted language.")[cite: 3]

    # 4. Insert Bets (Overwrite existing)[cite: 3]
    profile = supabase.table("profiles").select("full_name").eq("id", user.id).single().execute().data
    for q_id, pick_val in picks.items():
        supabase.table("user_bets").delete().eq("user_id", user.id).eq("question_id", q_id).execute()
        supabase.table("user_bets").insert({
            "user_id": user.id, "user_name": profile["full_name"], "week_number": week_number, 
            "question_id": q_id, "pick": pick_val, "wager_amount": int(wagers[q_id])
        }).execute()[cite: 3]
        
    if td_pick:
        supabase.table("touchdown_picks").delete().eq("user_id", user.id).eq("week_number", week_number).execute()
        supabase.table("touchdown_picks").insert({
            "user_id": user.id, "week_number": week_number, "player_name": td_pick, "is_correct": None
        }).execute()[cite: 3]

    return {"message": "Bets submitted successfully!"}

# ==========================================
# 7. ADMIN ENDPOINTS (Restricted)
# ==========================================
@app.post("/api/admin/grade")
async def grade_week(request: Request):
    user = get_current_user(request)
    supabase = get_supabase()
    profile = supabase.table("profiles").select("is_admin").eq("id", user.id).single().execute().data
    
    if not profile or not profile.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")[cite: 3]
        
    data = await request.json()
    week_number = data.get("week_number")
    winning_answers = data.get("answers") # Dict of {question_id: answer}
    
    for q_id, ans in winning_answers.items():
        supabase.table("weekly_questions").update({"winning_answer": ans}).eq("id", q_id).execute()[cite: 3]
        
    recalculate_all_user_balances(supabase)[cite: 3]
    return {"message": f"Week {week_number} graded and balances recalculated!"}
