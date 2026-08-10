import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client
from starlette.middleware.base import BaseHTTPMiddleware

# Import your modular routers (including dashboard and contact)
from routers import auth, bets, leagues, profile, admin, commish, contact, dashboard

class CommissionerCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.is_commissioner = False
        
        session_cookie = request.cookies.get("td_tokens_session")
        if session_cookie:
            try:
                token_data = json.loads(session_cookie)
                supabase = request.app.state.supabase
                access_token = token_data.get("access_token")
                
                user_res = supabase.auth.get_user(access_token)
                if user_res and user_res.user:
                    user = user_res.user
                    league_res = supabase.table("leagues").select("id").eq("commissioner_id", user.id).execute()
                    if league_res.data and len(league_res.data) > 0:
                        request.state.is_commissioner = True
            except Exception as e:
                print(f"Middleware Commish Check Error: {e}")
                
        response = await call_next(request)
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
    app.state.supabase = create_client(supabase_url, supabase_key)
    yield

app = FastAPI(
    title="Touchdown Tokens",
    description="Weekly NFL Predictions & Wagers Platform",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(CommissionerCheckMiddleware)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory="templates")
app.state.templates = templates  # Make templates easily accessible to routers if needed

# Register Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(bets.router, prefix="/bets", tags=["Bets & Gameplay"])
app.include_router(leagues.router, prefix="/leagues", tags=["Leagues & Standings"])
app.include_router.router(profile.router, prefix="/profile", tags=["Profile Management"]) if hasattr(profile.router, "router") else app.include_router(profile.router, prefix="/profile", tags=["Profile Management"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Portal"])
app.include_router(commish.router, prefix="/commish", tags=["Commissioner Portal"])
app.include_router(contact.router, tags=["Contact Us"])
app.include_router(dashboard.router, tags=["Dashboard"])

@app.get("/logout")
async def logout(request: Request):
    """Clears the session cookie and redirects user to home/login page."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="td_tokens_session")
    return response

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Delegates root URL handling directly to the dashboard module logic."""
    return await dashboard.render_dashboard_or_index(request)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_endpoint(request: Request):
    """Delegates /dashboard routing directly to the dashboard module logic."""
    return await dashboard.render_dashboard_or_index(request)

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.get("/auth/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(request=request, name="signup.html", context={"request": request})

@app.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request):
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
        context={"request": request, "profile": profile, "active_tokens": active_tokens}
    )

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
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
                
            bets_res = supabase.table("user_bets").select("*").eq("user_id", user.id).execute()
            if bets_res.data:
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
    return RedirectResponse(url="/profile", status_code=303)
