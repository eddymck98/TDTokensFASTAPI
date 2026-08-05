import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Connect to your existing Supabase database using environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Fetch profiles from your existing Supabase database
    profiles_res = supabase.table("profiles").select("*").execute()
    profiles = profiles_res.data if profiles_res.data else []
    return templates.TemplateResponse("index.html", {"request": request, "profiles": profiles})
