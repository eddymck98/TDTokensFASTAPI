from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.database import get_supabase_client
from utils.dependencies import require_auth
from utils.helpers import get_static_nfl_team_data

router = APIRouter(tags=["Bets"])
templates = Jinja2Templates(directory="templates")
supabase = get_supabase_client()
NFL_TEAM_DATA = get_static_nfl_team_data()

@router.get("/bets", response_class=HTMLResponse)
async def bets_page(request: Request, user=Depends(require_auth)):
    """Renders the weekly prediction slate and active question forms."""
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
    
    # Fetch available weeks
    weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).execute()
    available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else []
    current_week = available_weeks[-1] if available_weeks else 1
    
    # Fetch questions for the current week
    questions_res = supabase.table("weekly_questions").select("*").eq("week_number", current_week).order("question_number").execute()
    
    # Fetch existing user bets for this week
    existing_bets = supabase.table("user_bets").select("*").eq("user_id", user.id).eq("week_number", current_week).execute().data or []
    existing_bets_map = {b["question_id"]: b for b in existing_bets}
    
    # Fetch existing touchdown scorer pick
    existing_td = supabase.table("touchdown_picks").select("player_name").eq("user_id", user.id).eq("week_number", current_week).execute().data
    default_td = existing_td[0]["player_name"] if existing_td else ""

    return templates.TemplateResponse(request=request, name="bets.html", context={
        "request": request,
        "profile": profile,
        "week_number": current_week,
        "questions": questions_res.data if questions_res.data else [],
        "existing_bets": existing_bets_map,
        "default_td": default_td,
        "team_data": NFL_TEAM_DATA
    })

@router.post("/bets/submit")
async def submit_bets(request: Request, user=Depends(require_auth)):
    """Processes and locks in weekly matchup predictions and token wagers."""
    form_data = await request.form()
    week_number = int(form_data.get("week_number", 1))
    td_player = form_data.get("td_player", "").strip()
    
    profile = supabase.table("profiles").select("tokens, full_name").eq("id", user.id).single().execute().data
    available_tokens = profile.get("tokens", 10)
    
    wagers, picks = {}, {}
    total_wagered = 0
    
    for key, val in form_data.items():
        if key.startswith("pick_"):
            q_id = key.replace("pick_", "")
            picks[q_id] = val
        elif key.startswith("wager_"):
            q_id = key.replace("wager_", "")
            wager_val = int(val) if val else 0
            wagers[q_id] = wager_val
            total_wagered += wager_val

    if total_wagered > available_tokens:
        raise HTTPException(status_code=400, detail=f"Over-wagered! Allocated {total_wagered} tokens but only have {available_tokens} available.")
    
    # Save picks to Supabase
    for q_id, pick_val in picks.items():
        supabase.table("user_bets").delete().eq("user_id", user.id).eq("question_id", q_id).execute()
        supabase.table("user_bets").insert({
            "user_id": user.id,
            "user_name": profile["full_name"],
            "week_number": week_number,
            "question_id": q_id,
            "pick": pick_val,
            "wager_amount": wagers.get(q_id, 0)
        }).execute()
        
    # Save Touchdown Scorer pick
    if td_player:
        supabase.table("touchdown_picks").delete().eq("user_id", user.id).eq("week_number", week_number).execute()
        supabase.table("touchdown_picks").insert({
            "user_id": user.id,
            "week_number": week_number,
            "player_name": td_player,
            "is_correct": None
        }).execute()

    return RedirectResponse(url="/dashboard?success=bets_locked", status_code=status.HTTP_303_SEE_OTHER)
