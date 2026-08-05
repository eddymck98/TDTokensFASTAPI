import os
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from utils.database import get_supabase_client
from utils.dependencies import get_current_user
from routers import auth, bets, profile, leagues, admin

# This explicitly defines 'app' for Uvicorn
app = FastAPI(title="Touchdown Tokens")

# Mount your static CSS and assets folder
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
supabase = get_supabase_client()

# Register all feature routers
app.include_router(auth.router)
app.include_router(bets.router)
app.include_router(profile.router)
app.include_router(leagues.router)
app.include_router(admin.router)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(get_current_user)):
    """Main logged-in dashboard route."""
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    profile_data = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
    
    # Fetch latest week for active entries display
    weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).execute()
    db_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else [1]
    latest_week = db_weeks[-1] if db_weeks else 1
    
    # Fetch active user bets for this week
    user_bets = supabase.table("user_bets").select("*, weekly_questions(question_number, question_text)").eq("user_id", user.id).eq("week_number", latest_week).execute().data or []

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "request": request,
        "profile": profile_data,
        "latest_week": latest_week,
        "bets": user_bets
    })
