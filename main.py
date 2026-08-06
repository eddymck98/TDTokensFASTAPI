import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import your modular routers
from routers import auth, bets, leagues, profile, admin

app = FastAPI(
    title="Touchdown Tokens",
    description="Weekly NFL Predictions & Wagers Platform",
    version="2.0.0"
)

# Mount static directory for CSS and assets
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates directory
templates = Jinja2Templates(directory="templates")

# Register Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(bets.router, prefix="/bets", tags=["Bets & Gameplay"])
app.include_router(leagues.router, prefix="/leagues", tags=["Leagues & Standings"])
app.include_router(profile.router, prefix="/profile", tags=["Profile Management"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Portal"])

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Renders the primary application dashboard or login view."""
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("dashboard.html", {"request": request})
