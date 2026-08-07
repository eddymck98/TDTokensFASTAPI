import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client

# Import your modular routers
from routers import auth, bets, leagues, profile, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize and inject Supabase client into app state
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
    app.state.supabase = create_client(supabase_url, supabase_key)
    yield
    # Shutdown: Clean up resources if needed

app = FastAPI(
    title="Touchdown Tokens",
    description="Weekly NFL Predictions & Wagers Platform",
    version="2.0.0",
    lifespan=lifespan
)

# Get the absolute directory where main.py resides
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount static directory once using the absolute path
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configure Jinja2 templates directory
templates = Jinja2Templates(directory="templates")

# Register Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(bets.router, prefix="/bets", tags=["Bets & Gameplay"])
app.include_router(leagues.router, prefix="/leagues", tags=["Leagues & Standings"])
app.include_router(profile.router, prefix="/profile", tags=["Profile Management"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Portal"])

async def render_dashboard_or_index(request: Request):
    """Core logic to render either the dashboard (if logged in) or index (if logged out)."""
    session_cookie = request.cookies.get("td_tokens_session")
    
    if not session_cookie:
        return templates.TemplateResponse(request=request, name="index.html", context={"request": request})
    
    supabase = request.app.state.supabase
    
    try:
        token_data = json.loads(session_cookie)
        access_token = token_data.get("access_token")
        supabase.auth.set_session(access_token, token_data.get("refresh_token"))
        user = supabase.auth.get_user(access_token).user
        if not user:
            return templates.TemplateResponse(request=request, name="index.html", context={"request": request})
    except Exception:
        return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

    # --- 1. ISOLATED PROFILE FETCH ---
    try:
        user_email = user.email
        profile_res = supabase.table("profiles").select("*").eq("email", user_email).execute()
        
        current_profile = profile_res.data[0] if profile_res.data else {
            "tokens": 10, 
            "full_name": user_email.split('@')[0],
            "selected_title": "🏈 Gridiron Contender",
            "favorite_team": "🏈 Free Agent / Neutral",
            "is_admin": False
        }
        active_tokens = current_profile.get("tokens", 10)
    except Exception as e:
        print(f"Profile Fetch Error: {e}")
        current_profile = {
            "tokens": 10, 
            "full_name": "Error Loading Profile",
            "selected_title": "🏈 Gridiron Contender",
            "favorite_team": "🏈 Free Agent / Neutral",
            "is_admin": False
        }
        active_tokens = 10

    # --- 2. ISOLATED BETS, CONSENSUS & STATS FETCH ---
    available_weeks = []
    current_user_bets = []
    td_pick = None
    consensus_data = []
    personal_stats = {"total_bets": 0, "wins": 0, "losses": 0, "pending": 0, "tokens_wagered": 0}
    share_text = "🏈 Weekly Lock-Ins Loaded 🏈\n\nNo picks submitted yet."
    
    try:
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        if weeks_res.data:
            available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data])))
        
        if available_weeks:
            latest_week = available_weeks[-1]
            
            # Fetch bets without the risky relational join
            bets_res = supabase.table("user_bets").select("*").eq("user_id", user.id).eq("week_number", latest_week).execute()
            
            # Fetch questions manually to map them perfectly in Python
            q_res = supabase.table("weekly_questions").select("*").eq("week_number", latest_week).execute()
            questions_map = {q["id"]: q for q in q_res.data} if q_res.data else {}
            
            if bets_res.data:
                for b in bets_res.data:
                    q_id = b.get("question_id")
                    wq = questions_map.get(q_id, {})
                    
                    b["question_number"] = wq.get("question_number", 99)
                    b["question_text"] = wq.get("question_text", "Unknown Matchup")
                    
                    w_ans = wq.get("winning_answer", "Pending")
                    if w_ans in ["Yes", "No"]:
                        b["status_label"] = "Won ✅" if b.get("pick") == w_ans else "Lost ❌"
                    else:
                        b["status_label"] = "Pending ⏳"
                        
                    current_user_bets.append(b)
                    
                    # Update personal stats
                    personal_stats["tokens_wagered"] += b.get("wager_amount", 0)
                    if "Won" in b["status_label"]:
                        personal_stats["wins"] += 1
                    elif "Lost" in b["status_label"]:
                        personal_stats["losses"] += 1
                    else:
                        personal_stats["pending"] += 1
                
                # FIX: Sort bets via integer (fixes Q1, Q10, Q2 issue)
                current_user_bets = sorted(current_user_bets, key=lambda x: int(x.get("question_number", 99)) if str(x.get("question_number")).isdigit() else 99)
                personal_stats["total_bets"] = len(current_user_bets)
                
                # Generate Share Text
                share_lines = ["🏈 Weekly Lock-Ins Loaded 🏈\n"]
                for b in current_user_bets:
                    share_lines.append(f"Q{b['question_number']}: {b['pick']} ({b['wager_amount']} 🪙)")
                share_text = "\n".join(share_lines)
            
            # Fetch Touchdown Scorer Bonus
            td_res = supabase.table("touchdown_picks").select("*").eq("user_id", user.id).eq("week_number", latest_week).execute()
            if td_res.data:
                td_pick = td_res.data[0]
                td_status = td_pick.get("is_correct")
                if td_status is True:
                    td_pick["status_label"] = "Won ✅"
                    personal_stats["wins"] += 1
                elif td_status is False:
                    td_pick["status_label"] = "Lost ❌"
                    personal_stats["losses"] += 1
                else:
                    td_pick["status_label"] = "Pending ⏳"
                    personal_stats["pending"] += 1
                
                share_text += f"\n\nTD Bonus: {td_pick.get('player_name', '')}"

            # Fetch League Consensus
            all_bets = supabase.table("user_bets").select("question_id, pick, wager_amount").eq("week_number", latest_week).execute()
            if all_bets.data:
                q_stats = {}
                for b in all_bets.data:
                    qid = b["question_id"]
                    if qid not in q_stats:
                        q_stats[qid] = {
                            "yes_count": 0, "no_count": 0, "total_wager": 0, 
                            "q_num": questions_map.get(qid, {}).get("question_number", 99), 
                            "text": questions_map.get(qid, {}).get("question_text", "")
                        }
                    
                    if b["pick"] == "Yes":
                        q_stats[qid]["yes_count"] += 1
                    elif b["pick"] == "No":
                        q_stats[qid]["no_count"] += 1
                        
                    q_stats[qid]["total_wager"] += b.get("wager_amount", 0)
                
                for qid, stats in q_stats.items():
                    total_picks = stats["yes_count"] + stats["no_count"]
                    if total_picks > 0:
                        stats["yes_pct"] = int((stats["yes_count"] / total_picks) * 100)
                        stats["no_pct"] = int((stats["no_count"] / total_picks) * 100)
                    else:
                        stats["yes_pct"], stats["no_pct"] = 0, 0
                    consensus_data.append(stats)
                
                consensus_data = sorted(consensus_data, key=lambda x: int(x["q_num"]) if str(x["q_num"]).isdigit() else 99)
                
    except Exception as e:
        print(f"Bets Fetch Error: {e}")

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "request": request,
            "profile": current_profile,
            "active_tokens": active_tokens,
            "available_weeks": available_weeks,
            "current_user_bets": current_user_bets,
            "td_pick": td_pick,
            "personal_stats": personal_stats,
            "consensus_data": consensus_data,
            "share_text": share_text
        }
    )

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Renders the primary application dashboard or login view."""
    return await render_dashboard_or_index(request)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Renders the dashboard explicitly when hitting /dashboard."""
    return await render_dashboard_or_index(request)

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Renders the login template page."""
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.get("/auth/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Renders the signup template page."""
    return templates.TemplateResponse(request=request, name="signup.html", context={"request": request})

@app.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request):
    """Renders the game rules and guidelines page with profile context."""
    session_cookie = request.cookies.get("td_tokens_session")
    profile = None
    active_tokens = 10
    
    if session_cookie:
        try:
            supabase = request.app.state.supabase
            token_data = json.loads(session_cookie)
            supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
            user = supabase.auth.get_user(token_data.get("access_token")).user
            if user:
                profile_res = supabase.table("profiles").select("*").eq("email", user.email).execute()
                if profile_res.data:
                    profile = profile_res.data[0]
                    active_tokens = profile.get("tokens", 10)
        except Exception:
            pass

    return templates.TemplateResponse(
        request=request, 
        name="rules.html", 
        context={
            "request": request, 
            "profile": profile, 
            "active_tokens": active_tokens
        }
    )

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Renders user betting history."""
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/auth/login", status_code=303)
        
    supabase = request.app.state.supabase
    profile = None
    user_bets = []
    
    try:
        token_data = json.loads(session_cookie)
        access_token = token_data.get("access_token")
        supabase.auth.set_session(access_token, token_data.get("refresh_token"))
        user = supabase.auth.get_user(access_token).user
        
        if user:
            profile_res = supabase.table("profiles").select("*").eq("email", user.email).execute()
            if profile_res.data:
                profile = profile_res.data[0]
                
            # Fetch all past bets for the logged-in user
            bets_res = supabase.table("user_bets").select("*").eq("user_id", user.id).execute()
            if bets_res.data:
                # Add sorting or additional mapping here if you want to embellish the history
                user_bets = sorted(bets_res.data, key=lambda x: x.get("week_number", 0), reverse=True)
    except Exception as e:
        print(f"History Page Error: {e}")

    return templates.TemplateResponse(
        request=request, 
        name="history.html", 
        context={
            "request": request, 
            "profile": profile, 
            "active_tokens": profile.get("tokens", 10) if profile else 10,
            "user_bets": user_bets
        }
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Redirects Settings tab directly to Profile customization hub."""
    return RedirectResponse(url="/profile", status_code=303)

@app.get("/commish", response_class=HTMLResponse)
async def commish_page(request: Request):
    """Renders Commissioner hub for league owners and admins."""
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/auth/login", status_code=303)
        
    supabase = request.app.state.supabase
    profile = None
    
    try:
        token_data = json.loads(session_cookie)
        access_token = token_data.get("access_token")
        supabase.auth.set_session(access_token, token_data.get("refresh_token"))
        user = supabase.auth.get_user(access_token).user
        
        if user:
            profile_res = supabase.table("profiles").select("*").eq("email", user.email).execute()
            if profile_res.data:
                profile = profile_res.data[0]
    except Exception as e:
        print(f"Commish Page Error: {e}")

    return templates.TemplateResponse(
        request=request, 
        name="commish.html", 
        context={
            "request": request, 
            "profile": profile, 
            "active_tokens": profile.get("tokens", 10) if profile else 10
        }
    )
