import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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

    # --- 2. ISOLATED BETS & WEEKS FETCH ---
    available_weeks = []
    current_user_bets = []
    
    try:
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        if weeks_res.data:
            available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data])))
        
        if available_weeks:
            latest_week = available_weeks[-1]
            
            # Fetch bets without the risky relational join
            bets_res = supabase.table("user_bets").select("*").eq("user_id", user.id).eq("week_number", latest_week).execute()
            
            if bets_res.data:
                # Fetch questions manually to map them perfectly in Python
                q_res = supabase.table("weekly_questions").select("*").eq("week_number", latest_week).execute()
                questions_map = {q["id"]: q for q in q_res.data} if q_res.data else {}
                
                for b in bets_res.data:
                    q_id = b.get("question_id")
                    wq = questions_map.get(q_id, {})
                    
                    b["question_number"] = wq.get("question_number", "?")
                    b["question_text"] = wq.get("question_text", "Unknown Matchup")
                    
                    w_ans = wq.get("winning_answer", "Pending")
                    if w_ans in ["Yes", "No"]:
                        b["status_label"] = "Won ✅" if b.get("pick") == w_ans else "Lost ❌"
                    else:
                        b["status_label"] = "Pending ⏳"
                        
                    current_user_bets.append(b)
                
                # Sort bets so Q1, Q2, Q3 display in order
                current_user_bets = sorted(current_user_bets, key=lambda x: str(x.get("question_number", "0")))
                
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
            "current_user_bets": current_user_bets
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
