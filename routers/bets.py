import os
import json
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from supabase import Client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_supabase(request: Request) -> Client:
    return request.app.state.supabase

@router.get("/bets", response_class=HTMLResponse)
async def get_bets_page(request: Request, supabase: Client = Depends(get_supabase)):
    # Session verification logic matching main.py cookie management
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/", status_code=303)
    
    try:
        token_data = json.loads(session_cookie)
        acc_token = token_data.get("access_token")
        ref_token = token_data.get("refresh_token")
        auth_res = supabase.auth.set_session(acc_token, ref_token)
        user = auth_res.user
        if not user:
            return RedirectResponse(url="/", status_code=303)
    except Exception:
        return RedirectResponse(url="/", status_code=303)

    # Fetch active weeks and questions for betting pool
    try:
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else []
        
        profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
    except Exception:
        available_weeks = []
        profile = {}

    return templates.TemplateResponse("bets.html", {
        "request": request,
        "user": user,
        "profile": profile,
        "available_weeks": available_weeks
    })

@router.post("/bets/submit")
async def submit_weekly_bets(
    request: Request,
    week_number: int = Form(...),
    touchdown_pick: str = Form(""),
    supabase: Client = Depends(get_supabase)
):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    
    try:
        token_data = json.loads(session_cookie)
        supabase.auth.set_session(token_data.get("access_token"), token_data.get("refresh_token"))
        user = supabase.auth.get_user().user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user session.")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    form_data = await request.form()
    
    # Process dynamically submitted question picks and wagers from form fields
    try:
        profile = supabase.table("profiles").select("full_name, tokens").eq("id", user.id).single().execute().data
        
        # Clear out existing bets for this specific week before inserting new overrides
        supabase.table("user_bets").delete().eq("user_id", user.id).eq("week_number", week_number).execute()
        
        # Parse dynamic inputs sent from the HTML frontend form elements
        question_ids = set()
        for key in form_data.keys():
            if key.startswith("pick_"):
                parts = key.split("_")
                if len(parts) >= 3:
                    question_ids.add(parts[2])

        total_wagered = 0
        bets_to_insert = []
        
        for q_id in question_ids:
            pick_val = form_data.get(f"pick_{week_number}_{q_id}", "Yes")
            wager_val = int(form_data.get(f"wager_{week_number}_{q_id}", 0))
            total_wagered += wager_val

            # Safely cast question_id to integer if the schema expects integer IDs, avoiding type mismatch errors
            try:
                parsed_q_id = int(q_id)
            except ValueError:
                parsed_q_id = q_id

            bets_to_insert.append({
                "user_id": user.id,
                "user_name": profile.get("full_name", "Player"),
                "week_number": week_number,
                "question_id": parsed_q_id,
                "pick": pick_val,
                "wager_amount": wager_val
            })

        # Validate token constraints
        if total_wagered > profile.get("tokens", 10):
            raise HTTPException(status_code=400, detail="Token allocation exceeds available balance.")

        # Batch write user picks
        for bet in bets_to_insert:
            supabase.table("user_bets").insert(bet).execute()

        # Handle Touchdown Scorer Bonus Pick
        if touchdown_pick.strip():
            supabase.table("touchdown_picks").delete().eq("user_id", user.id).eq("week_number", week_number).execute()
            supabase.table("touchdown_picks").insert({
                "user_id": user.id,
                "week_number": week_number,
                "player_name": touchdown_pick.strip(),
                "is_correct": None
            }).execute()

        return RedirectResponse(url="/bets?success=bets_locked", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
