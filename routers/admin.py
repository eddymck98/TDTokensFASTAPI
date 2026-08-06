from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import os, pandas as pd
from supabase import Client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Dependency injection for Supabase and Authentication (adjust according to your project setup)
def get_supabase(request: Request) -> Client:
    return request.app.state.supabase # or reference your global client instance

def contains_profanity(text: str) -> bool:
    PROFANITY_FILTER = ["damn", "hell", "crap", "shit", "fuck", "bitch", "asshole", "dick", "cunt", "bastard"]
    if not text: return False
    text_lower = text.lower(); words = text_lower.split()
    return any(p_word in text_lower or any(p_word == w for w in words) for p_word in PROFANITY_FILTER)

def recalculate_all_user_balances(supabase_client: Client):
    try:
        all_profiles = supabase_client.table("profiles").select("id").execute().data
        if not all_profiles: return
        for prof in all_profiles:
            uid = prof["id"]
            # Fetch bets safely without relying on broken embedded resource joins
            u_bets = supabase_client.table("user_bets").select("week_number, wager_amount, pick, question_id").eq("user_id", uid).execute().data
            
            # Fetch questions for winning answer matching independently
            questions_res = supabase_client.table("weekly_questions").select("id, week_number, winning_answer").execute().data
            q_winning_map = {q["id"]: q["winning_answer"] for q in questions_res} if questions_res else {}

            u_td = supabase_client.table("touchdown_picks").select("week_number, is_correct").eq("user_id", uid).eq("is_correct", True).execute().data
            td_wins_map = {td["week_number"]: 5 for td in u_td}
            
            curr_tokens = 10
            if u_bets or td_wins_map:
                for w in sorted(list(set([b["week_number"] for b in u_bets] + list(td_wins_map.keys())))):
                    for b in [b for b in u_bets if b["week_number"] == w]:
                        # Map winning answer safely via dictionary lookup using question_id
                        w_ans = q_winning_map.get(b.get("question_id"))
                        if w_ans in ["Yes", "No"]:
                            curr_tokens += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
                    if w in td_wins_map: curr_tokens += 5
            supabase_client.table("profiles").update({"tokens": max(0, curr_tokens)}).eq("id", uid).execute()
    except Exception: pass

@router.get("/", response_class=HTMLResponse)
async def admin_portal_landing(request: Request):
    """Renders the central admin tab view or control hub."""
    return templates.TemplateResponse(request=request, name="admin.html", context={"request": request})

@router.post("/publish")
async def admin_publish_questions(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    form_data = await request.form()
    # Process and publish 10 weekly question payloads mirroring the Streamlit form logic
    for i in range(1, 11):
        prompt = form_data.get(f"prompt_{i}", "")
        away_t = form_data.get(f"away_{i}", "🏈 Free Agent / Neutral")
        home_t = form_data.get(f"home_{i}", "🏈 Free Agent / Neutral")
        if contains_profanity(prompt):
            raise HTTPException(status_code=400, detail="Restricted language detected in question prompt.")
        
        combined_text = f"{prompt.strip()} | MATCHUP: {away_t} @ {home_t}"
        existing = supabase.table("weekly_questions").select("id").eq("week_number", week_number).eq("question_number", i).execute().data
        if existing:
            supabase.table("weekly_questions").update({"question_text": combined_text}).eq("id", existing[0]["id"]).execute()
        else:
            supabase.table("weekly_questions").insert({"week_number": week_number, "question_number": i, "question_text": combined_text, "winning_answer": "Pending"}).execute()
    
    return RedirectResponse(url="/?success=questions_published", status_code=303)

@router.post("/schedule")
async def admin_save_lockout(
    request: Request,
    week_number: int = Form(...),
    lockout_iso: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    supabase.table("weekly_questions").delete().eq("week_number", week_number).ilike("winning_answer", "LOCKTIME:%").execute()
    supabase.table("weekly_questions").insert({
        "week_number": week_number,
        "question_number": 99,
        "question_text": "LOCKTIME SCHEDULER",
        "winning_answer": f"LOCKTIME:{lockout_iso}"
    }).execute()
    return RedirectResponse(url="/?success=lockout_saved", status_code=303)

@router.post("/live")
async def admin_grade_live(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    form_data = await request.form()
    # Extract question results and evaluate user token balances
    questions = supabase.table("weekly_questions").select("id, question_number").eq("week_number", week_number).lt("question_number", 11).execute().data
    for q in questions:
        ans = form_data.get(f"win_ans_{q['id']}")
        if ans in ["Yes", "No"]:
            supabase.table("weekly_questions").update({"winning_answer": ans}).eq("id", q["id"]).execute()
            
    recalculate_all_user_balances(supabase)
    return RedirectResponse(url="/?success=week_graded", status_code=303)

@router.post("/adjust")
async def admin_bulk_adjust_tokens(
    user_id: str = Form(...),
    adjustment_type: str = Form(...),
    amount: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    prof = supabase.table("profiles").select("tokens").eq("id", user_id).single().execute().data
    if prof:
        current_tokens = prof.get("tokens", 10)
        if adjustment_type == "add":
            new_tokens = current_tokens + amount
        elif adjustment_type == "subtract":
            new_tokens = max(0, current_tokens - amount)
        else:
            new_tokens = amount
        supabase.table("profiles").update({"tokens": new_tokens}).eq("id", user_id).execute()
    return RedirectResponse(url="/?success=tokens_adjusted", status_code=303)

@router.post("/control")
async def admin_app_access_control(
    signin_locked: bool = Form(False),
    signup_locked: bool = Form(False),
    supabase: Client = Depends(get_supabase)
):
    supabase.table("weekly_questions").delete().eq("week_number", 998).execute()
    supabase.table("weekly_questions").insert({"week_number": 998, "question_number": 99, "question_text": "SIGNIN LOCK SETTING", "winning_answer": "LOCKED" if signin_locked else "UNLOCKED"}).execute()
    
    supabase.table("weekly_questions").delete().eq("week_number", 997).execute()
    supabase.table("weekly_questions").insert({"week_number": 997, "question_number": 99, "question_text": "SIGNUP LOCK SETTING", "winning_answer": "LOCKED" if signup_locked else "UNLOCKED"}).execute()
    
    return RedirectResponse(url="/?success=access_controls_updated", status_code=303)
