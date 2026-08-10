import os
import json
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from supabase import Client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_supabase(request: Request) -> Client:
    return request.app.state.supabase

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
            u_bets = supabase_client.table("user_bets").select("week_number, wager_amount, pick, question_id").eq("user_id", uid).execute().data
            
            questions_res = supabase_client.table("weekly_questions").select("id, week_number, winning_answer").execute().data
            q_winning_map = {q["id"]: q["winning_answer"] for q in questions_res} if questions_res else {}

            u_td = supabase_client.table("touchdown_picks").select("week_number, is_correct").eq("user_id", uid).eq("is_correct", True).execute().data
            td_wins_map = {td["week_number"]: 5 for td in u_td}
            
            curr_tokens = 10
            if u_bets or td_wins_map:
                for w in sorted(list(set([b["week_number"] for b in u_bets] + list(td_wins_map.keys())))):
                    for b in [b for b in u_bets if b["week_number"] == w]:
                        w_ans = q_winning_map.get(b.get("question_id"))
                        if w_ans in ["Yes", "No"]:
                            curr_tokens += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
                    if w in td_wins_map: curr_tokens += 5
            supabase_client.table("profiles").update({"tokens": max(0, curr_tokens)}).eq("id", uid).execute()
    except Exception: pass

@router.get("/", response_class=HTMLResponse)
async def admin_portal_landing(request: Request, week: Optional[int] = None):
    session_cookie = request.cookies.get("td_tokens_session")
    if not session_cookie:
        return RedirectResponse(url="/auth/login", status_code=303)

    supabase = request.app.state.supabase

    try:
        token_data = json.loads(session_cookie)
        access_token = token_data.get("access_token")
        supabase.auth.set_session(access_token, token_data.get("refresh_token"))
        user = supabase.auth.get_user(access_token).user
        
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)

        profile_res = supabase.table("profiles").select("*").eq("email", user.email).execute()
        current_profile = profile_res.data[0] if profile_res.data else {
            "full_name": user.email.split('@')[0],
            "is_admin": False,
            "tokens": 10
        }
        
        if not current_profile.get("is_admin", False):
            return RedirectResponse(url="/dashboard", status_code=303)

    except Exception as e:
        print(f"Admin Auth Error: {e}")
        return RedirectResponse(url="/auth/login", status_code=303)

    # Fetch all active weeks to populate pill navigation & default to newest
    available_weeks = []
    target_week = 1
    is_week_closed = False
    is_published = True
    lockout_date_val = ""
    lockout_time_val = ""

    try:
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else [1]
        
        # Default to requested week or the newest/latest week
        target_week = week if week and week in available_weeks else available_weeks[-1]

        # Check if this target week is closed (Question 98 flag)
        status_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", target_week).eq("question_number", 98).execute()
        if status_res.data and status_res.data[0].get("winning_answer") == "CLOSED":
            is_week_closed = True

        # Check publishing status (Default to True/published if row/column doesn't explicitly restrict it, or check via custom metadata)
        pub_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", target_week).eq("question_number", 96).execute()
        if pub_res.data and pub_res.data[0].get("winning_answer") == "UNPUBLISHED":
            is_published = False

        # Fetch lockout schedule if stored and parse into separate date & time parts for UK boxes
        lock_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", target_week).eq("question_number", 99).ilike("winning_answer", "LOCKTIME:%").execute()
        if lock_res.data:
            raw_lock = lock_res.data[0].get("winning_answer", "")
            if ":" in raw_lock:
                iso_str = raw_lock.split(":", 1)[1].replace("Z", "")
                if "T" in iso_str:
                    parts = iso_str.split("T")
                    lockout_date_val = parts[0]
                    lockout_time_val = parts[1][:5] # HH:MM format

    except Exception as e:
        print(f"Error fetching weeks for admin: {e}")

    # Fetch all profiles to populate user dropdowns in the UI
    all_profiles = []
    try:
        prof_res = supabase.table("profiles").select("id, full_name, email").execute()
        all_profiles = prof_res.data if prof_res.data else []
    except Exception as e:
        print(f"Error fetching profiles for admin: {e}")

    # Fetch Existing Questions for Target Week
    existing_questions = []
    try:
        q_res = (
            supabase.table("weekly_questions")
            .select("*")
            .eq("week_number", target_week)
            .execute()
        )
        existing_questions = q_res.data if q_res.data else []
    except Exception as e:
        print(f"Admin Questions Fetch Error: {e}")

    questions_map = {}
    for q in existing_questions:
        qn = q.get("question_number")
        if qn >= 96: # Skip system utility rows (96, 98, 99, etc.)
            continue
        q_text = q.get("question_text", "")
        
        prompt = q_text
        away_team = "🏈 Free Agent / Neutral"
        home_team = "🏈 Free Agent / Neutral"
        
        if " | MATCHUP: " in q_text:
            parts = q_text.split(" | MATCHUP: ")
            prompt = parts[0]
            teams = parts[1].split(" @ ")
            if len(teams) == 2:
                away_team = teams[0]
                home_team = teams[1]
                
        questions_map[qn] = {
            "id": q.get("id"),
            "question_number": qn,
            "question_text": prompt,
            "winning_answer": q.get("winning_answer", "Pending"),
            "away_team": away_team,
            "home_team": home_team
        }

    # Fetch User Touchdown Picks and attach names map
    user_td_picks = []
    try:
        td_res = supabase.table("touchdown_picks").select("*").eq("week_number", target_week).execute()
        raw_tds = td_res.data if td_res.data else []
        
        profile_name_map = {p["id"]: p.get("full_name", p.get("email", "Unknown")) for p in all_profiles}
        
        for td in raw_tds:
            td["user_name"] = profile_name_map.get(td["user_id"], "Unknown User")
            user_td_picks.append(td)
    except Exception as e:
        print(f"Admin TD Picks Fetch Error: {e}")

    return templates.TemplateResponse(
        request,
        name="admin.html",
        context={
            "request": request,
            "profile": current_profile,
            "active_tokens": current_profile.get("tokens", 10),
            "available_weeks": available_weeks,
            "target_week": target_week,
            "is_week_closed": is_week_closed,
            "is_published": is_published,
            "lockout_date_val": lockout_date_val,
            "lockout_time_val": lockout_time_val,
            "questions_map": questions_map,
            "user_td_picks": user_td_picks,
            "all_profiles": all_profiles
        }
    )

@router.post("/create-week")
async def admin_create_new_week(
    request: Request,
    supabase: Client = Depends(get_supabase)
):
    """Creates the next consecutive week number in the database as an unpublished draft."""
    try:
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        existing_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else [1]
        next_week = existing_weeks[-1] + 1 if existing_weeks else 1

        # Insert question 1 as draft and mark week 96 as UNPUBLISHED
        supabase.table("weekly_questions").insert({
            "week_number": next_week,
            "question_number": 1,
            "question_text": f"Week {next_week} Opening Matchup | MATCHUP: 🏈 Free Agent / Neutral @ 🏈 Free Agent / Neutral",
            "winning_answer": "Pending"
        }).execute()

        supabase.table("weekly_questions").insert({
            "week_number": next_week,
            "question_number": 96,
            "question_text": "PUBLISH STATUS",
            "winning_answer": "UNPUBLISHED"
        }).execute()

        return RedirectResponse(url=f"/admin?week={next_week}", status_code=303)
    except Exception as e:
        print(f"Error creating new week: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/publish")
async def admin_publish_questions(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    # Guard check: prevent publishing/editing if the week is closed
    status_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", week_number).eq("question_number", 98).execute()
    if status_res.data and status_res.data[0].get("winning_answer") == "CLOSED":
        raise HTTPException(status_code=403, detail="Cannot modify questions for a closed/locked week.")

    form_data = await request.form()
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
    
    return RedirectResponse(url=f"/admin?week={week_number}&success=questions_published", status_code=303)

@router.post("/week/set-lockout")
async def set_lockout(
    request: Request,
    week_number: int = Form(...),
    lockout_date: str = Form(...),
    lockout_time_val: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    iso_time = f"{lockout_date}T{lockout_time_val}:00Z" if lockout_date and lockout_time_val else ""
    supabase.table("weekly_questions").delete().eq("week_number", week_number).eq("question_number", 99).execute()
    supabase.table("weekly_questions").insert({
        "week_number": week_number,
        "question_number": 99,
        "question_text": "LOCKTIME SCHEDULER",
        "winning_answer": f"LOCKTIME:{iso_time}"
    }).execute()
    return RedirectResponse(url=f"/admin?week={week_number}&success=lockout_updated", status_code=303)

@router.post("/week/clear-lockout")
async def clear_lockout(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    supabase.table("weekly_questions").delete().eq("week_number", week_number).eq("question_number", 99).execute()
    return RedirectResponse(url=f"/admin?week={week_number}&success=lockout_cleared", status_code=303)

@router.post("/week/publish")
async def publish_week(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    supabase.table("weekly_questions").delete().eq("week_number", week_number).eq("question_number", 96).execute()
    return RedirectResponse(url=f"/admin?week={week_number}&success=published", status_code=303)

@router.post("/week/unpublish")
async def unpublish_week(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    supabase.table("weekly_questions").upsert({
        "week_number": week_number,
        "question_number": 96,
        "question_text": "PUBLISH STATUS",
        "winning_answer": "UNPUBLISHED"
    }, on_conflict="week_number,question_number").execute()
    return RedirectResponse(url=f"/admin?week={week_number}&success=unpublished", status_code=303)

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
    return RedirectResponse(url=f"/admin?week={week_number}&success=lockout_saved", status_code=303)

@router.post("/toggle-week-status")
async def toggle_week_status(
    request: Request,
    week_number: int = Form(...),
    action: str = Form(...),  # 'close' or 'reopen'
    supabase: Client = Depends(get_supabase)
):
    """Closes or Reopens a week by updating Question 98 status."""
    try:
        status_val = "CLOSED" if action == "close" else "OPEN"
        
        existing = supabase.table("weekly_questions").select("id").eq("week_number", week_number).eq("question_number", 98).execute()
        
        if existing.data:
            supabase.table("weekly_questions").update({"winning_answer": status_val}).eq("week_number", week_number).eq("question_number", 98).execute()
        else:
            supabase.table("weekly_questions").insert({
                "week_number": week_number,
                "question_number": 98,
                "question_text": "WEEK STATUS",
                "winning_answer": status_val
            }).execute()

        return RedirectResponse(url=f"/admin?week={week_number}", status_code=303)
    except Exception as e:
        print(f"Error toggling week status: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/close-week")
async def close_weekly_slate(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    try:
        supabase.table("weekly_questions").upsert({
            "week_number": week_number,
            "question_number": 98,
            "question_text": "WEEK STATUS",
            "winning_answer": "CLOSED"
        }, on_conflict="week_number,question_number").execute()
        
        return RedirectResponse(url=f"/admin?week={week_number}&success=week_closed", status_code=303)
    except Exception as e:
        print(f"Error closing week: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/live")
async def admin_grade_live(
    request: Request,
    week_number: int = Form(...),
    supabase: Client = Depends(get_supabase)
):
    form_data = await request.form()
    
    questions = supabase.table("weekly_questions").select("id, question_number").eq("week_number", week_number).lt("question_number", 11).execute().data
    for q in questions:
        ans = form_data.get(f"win_ans_{q['id']}")
        if ans in ["Yes", "No", "Pending"]:
            supabase.table("weekly_questions").update({"winning_answer": ans}).eq("id", q["id"]).execute()
            
    for key, val in form_data.items():
        if key.startswith("td_grade_"):
            try:
                td_record_id = key.replace("td_grade_", "")
                if val == "True":
                    is_correct_val = True
                elif val == "False":
                    is_correct_val = False
                else:
                    is_correct_val = None

                supabase.table("touchdown_picks").update({"is_correct": is_correct_val}).eq("id", td_record_id).execute()
            except Exception as e:
                print(f"Error updating TD pick grade: {e}")

    recalculate_all_user_balances(supabase)
    return RedirectResponse(url=f"/admin?week={week_number}&success=week_graded", status_code=303)

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
    return RedirectResponse(url="/admin?success=tokens_adjusted", status_code=303)

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
    
    return RedirectResponse(url="/admin?success=access_controls_updated", status_code=303)
