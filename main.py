import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    profiles_res = supabase.table("profiles").select("*").execute()
    profiles = profiles_res.data if profiles_res.data else []
    
    # FIXED: Using the modern keyword arguments for TemplateResponse
    return templates.TemplateResponse(
        request, 
        "index.html", 
        {"request": request, "profiles": profiles}
    )
