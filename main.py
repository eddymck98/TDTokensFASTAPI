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
        supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
        user = supabase.auth.get_user().user
        if not user:
            return templates.TemplateResponse(request=request, name="index.html", context={"request": request})
    except Exception:
        return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

    try:
        # Safely query profile without using .single()
        profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
        current_profile = profile_res.data[0] if profile_res.data else {
            "tokens": 10, 
            "full_name": "Gridiron Contender",
            "selected_title": "🏈 Gridiron Contender",
            "favorite_team": "🏈 Free Agent / Neutral"
        }
        
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else []
        
        current_user_bets = []
        if available_weeks:
            latest_week = available_weeks[-1]
            bets_res = supabase.table("user_bets").select("*, weekly_questions(question_number, question_text, winning_answer)").eq("user_id", user.id).eq("week_number", latest_week).execute()
            
            if bets_res.data:
                for b in bets_res.data:
                    wq = b.get("weekly_questions") or {}
                    b["question_number"] = wq.get("question_number", "?")
                    b["question_text"] = wq.get("question_text", "Unknown Matchup")
                    
                    w_ans = wq.get("winning_answer", "Pending")
                    if w_ans in ["Yes", "No"]:
                        b["status_label"] = "Won ✅" if b["pick"] == w_ans else "Lost ❌"
                    else:
                        b["status_label"] = "Pending ⏳"
                    current_user_bets.append(b)
                    
    except Exception as e:
        current_profile = {
            "tokens": 10, 
            "full_name": "Gridiron Contender",
            "selected_title": "🏈 Gridiron Contender",
            "favorite_team": "🏈 Free Agent / Neutral"
        }
        available_weeks = []
        current_user_bets = []

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "request": request,
            "profile": current_profile,
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
    """Renders the game rules and guidelines page."""
    return templates.TemplateResponse(request=request, name="rules.html", context={"request": request})
