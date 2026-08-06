from datetime import datetime, timezone
import random
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from utils.database import supabase
from utils.dependencies import get_current_user
from utils.helpers import NFL_TEAM_DATA, contains_profanity

router = APIRouter(prefix="/bets", tags=["Bets"])
templates = Jinja2Templates(directory="templates")

NFL_TEAMS = list(NFL_TEAM_DATA.keys())

def get_true_global_token_balance(target_user_id: str) -> int:
    """Retrieves the true global token balance matching app.py."""
    try:
        res = supabase.table("profiles").select("tokens").eq("id", target_user_id).single().execute()
        return max(0, (res.data or {}).get("tokens", 10))
    except Exception:
        return 10


@router.get("/", response_class=HTMLResponse)
async def view_bets_page(
    request: Request,
    week: Optional[int] = None,
    user_auth: dict = Depends(get_current_user)
):
    """Renders the Weekly Predictions & Wagers tab matching app.py exactly."""
    user_id = user_auth["id"]
    profile_res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = profile_res.data if profile_res and profile_res.data else {}

    # Fetch available weeks excluding system metadata markers
    weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
    db_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else []

    # Filter out fully closed/graded weeks
    active_unscored_weeks = []
    for w in db_weeks:
        week_status_row = supabase.table("weekly_questions").select("winning_answer").eq("week_number", w).eq("question_number", 96).execute().data
        is_closed = week_status_row and week_status_row[0]["winning_answer"] == "CLOSED"
        if not is_closed:
            w_qs_check = supabase.table("weekly_questions").select("winning_answer").eq("week_number", w).neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
            if w_qs_check and all(q["winning_answer"] in ["Yes", "No"] for q in w_qs_check):
                is_closed = True
        if not is_closed:
            active_unscored_weeks.append(w)

    selected_week = week or (active_unscored_weeks[-1] if active_unscored_weeks else (db_weeks[-1] if db_weeks else 1))

    # Fetch questions for selected week
    questions_res = supabase.table("weekly_questions").select("*").eq("week_number", selected_week).order("question_number").execute()
    questions = questions_res.data if questions_res.data else []

    # Check Lockout status
    is_locked = False
    lock_time_remaining_str = None
    lock_time_row = [q for q in questions if q.get("winning_answer", "").startswith("LOCKTIME:")]
    
    if lock_time_row:
        try:
            lock_dt = datetime.fromisoformat(lock_time_row[0]["winning_answer"].replace("LOCKTIME:", "")).replace(tzinfo=timezone.utc)
            total_seconds_left = int((lock_dt - datetime.now(timezone.utc)).total_seconds())
            if total_seconds_left <= 0:
                is_locked = True
            else:
                days, remainder = divmod(total_seconds_left, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                lock_time_remaining_str = f"{f'{days}d ' if days > 0 else ''}{hours}h {minutes}m {seconds}s remaining"
        except Exception:
            pass

    if any(q.get("winning_answer") == "LOCKED" for q in questions):
        is_locked = True

    true_global_tokens = get_true_global_token_balance(user_id)

    # Fetch existing user bets & touchdown picks for this week
    all_week_bets = supabase.table("user_bets").select("question_id, pick, wager_amount").eq("user_id", user_id).eq("week_number", selected_week).execute().data or []
    existing_bets_map = {b["question_id"]: b for b in all_week_bets}

    existing_td = supabase.table("touchdown_picks").select("player_name").eq("user_id", user_id).eq("week_number", selected_week).execute().data or []
    default_td_pick = existing_td[0]["player_name"] if existing_td else ""

    # Parse questions into structured items for template rendering
    formatted_questions = []
    for q in questions:
        if q.get("winning_answer", "").startswith("LOCKTIME:"):
            continue
        
        full_q_text = q["question_text"]
        away_team_name = "🏈 Free Agent / Neutral"
        home_team_name = "🏈 Free Agent / Neutral"
        prompt_text = full_q_text

        if " | MATCHUP: " in full_q_text:
            prompt_text, matchup_str = full_q_text.split(" | MATCHUP: ")
            if " @ " in matchup_str:
                split_teams = matchup_str.split(" @ ")
                away_team_name = split_teams[0] if split_teams[0] in NFL_TEAMS else away_team_name
                home_team_name = split_teams[1] if split_teams[1] in NFL_TEAMS else home_team_name

        away_info = NFL_TEAM_DATA.get(away_team_name, NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
        home_info = NFL_TEAM_DATA.get(home_team_name, NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
        prev_bet = existing_bets_map.get(q["id"], {})

        formatted_questions.append({
            "id": q["id"],
            "number": q["question_number"],
            "prompt": prompt_text,
            "away_name": away_team_name,
            "away_logo": away_info["logo"],
            "home_name": home_team_name,
            "home_logo": home_info["logo"],
            "default_pick": prev_bet.get("pick", "Yes"),
            "default_wager": prev_bet.get("wager_amount", 0)
        })

    return templates.TemplateResponse("bets.html", {
        "request": request,
        "profile": profile,
        "active_weeks": active_unscored_weeks,
        "selected_week": selected_week,
        "is_locked": is_locked,
        "lock_time_remaining": lock_time_remaining_str,
        "true_tokens": true_global_tokens,
        "questions": formatted_questions,
        "default_td_pick": default_td_pick,
        "msg": request.query_params.get("msg")
    })


@router.post("/submit")
async def submit_weekly_bets(
    request: Request,
    selected_week: int = Form(...),
    td_pick: Optional[str] = Form(""),
    user_auth: dict = Depends(get_current_user)
):
    """Handles secure submission of weekly matchup predictions, token wagers, and touchdown scorer picks matching app.py."""
    user_id = user_auth["id"]
    profile_res = supabase.table("profiles").select("full_name").eq("id", user_id).single().execute()
    profile = profile_res.data if profile_res and profile_res.data else {}
    full_name = profile.get("full_name", "Player")

    true_tokens = get_true_global_token_balance(user_id)
    form_data = await request.form()

    if td_pick and contains_profanity(td_pick):
        raise HTTPException(status_code=400, detail="Restricted language detected in Touchdown Scorer player name.")

    # Parse picks and wagers from form data
    question_ids = []
    wagers = {}
    picks = {}

    for key, val in form_data.items():
        if key.startswith("pick_"):
            q_id = key.replace("pick_", "")
            picks[q_id] = val
            if q_id not in question_ids:
                question_ids.append(q_id)
        elif key.startswith("wager_"):
            q_id = key.replace("wager_", "")
            try:
                wagers[q_id] = int(val)
            except ValueError:
                wagers[q_id] = 0

    total_wagered = sum(wagers.values())
    if total_wagered > true_tokens:
        raise HTTPException(status_code=400, detail=f"Cannot wager {total_wagered} tokens! You only have {true_tokens} tokens available.")

    # Execute database writes matching app.py transaction behavior
    for q_id in question_ids:
        pick_val = picks.get(q_id, "Yes")
        wager_amt = wagers.get(q_id, 0)
        
        supabase.table("user_bets").delete().eq("user_id", user_id).eq("question_id", q_id).execute()
        supabase.table("user_bets").insert({
            "user_id": user_id,
            "user_name": full_name,
            "week_number": selected_week,
            "question_id": q_id,
            "pick": pick_val,
            "wager_amount": wager_amt
        }).execute()

    if td_pick:
        supabase.table("touchdown_picks").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
        supabase.table("touchdown_picks").insert({
            "user_id": user_id,
            "week_number": selected_week,
            "player_name": td_pick.strip(),
            "is_correct": None
        }).execute()

    return RedirectResponse(url=f"/bets?week={selected_week}&msg=Bets+Successfully+Locked+In", status_code=303)


@router.post("/clear")
async def clear_weekly_bets(selected_week: int = Form(...), user_auth: dict = Depends(get_current_user)):
    """Clears all picks and wagers for the selected week matching app.py."""
    user_id = user_auth["id"]
    supabase.table("user_bets").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
    supabase.table("touchdown_picks").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
    return RedirectResponse(url=f"/bets?week={selected_week}&msg=Weekly+Bets+Cleared", status_code=303)


@router.post("/lucky")
async def feeling_lucky_randomize(selected_week: int = Form(...), user_auth: dict = Depends(get_current_user)):
    """Executes the random 'Feeling Lucky' pick and token distribution matching app.py."""
    user_id = user_auth["id"]
    profile_res = supabase.table("profiles").select("full_name").eq("id", user_id).single().execute()
    profile = profile_res.data if profile_res and profile_res.data else {}
    full_name = profile.get("full_name", "Player")

    true_tokens = get_true_global_token_balance(user_id)
    if true_tokens <= 0:
        raise HTTPException(status_code=400, detail="You have 0 tokens available to randomize.")

    questions_res = supabase.table("weekly_questions").select("*").eq("week_number", selected_week).execute()
    questions = [q for q in (questions_res.data or []) if not q.get("winning_answer", "").startswith("LOCKTIME:")]

    if not questions:
        raise HTTPException(status_code=400, detail="No active questions found to randomize.")

    # Clear existing bets for the week
    supabase.table("user_bets").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()

    # Distribute available tokens randomly across questions
    token_allocations = {q["id"]: 0 for q in questions}
    for _ in range(true_tokens):
        token_allocations[random.choice(questions)["id"]] += 1

    for q_item in questions:
        supabase.table("user_bets").insert({
            "user_id": user_id,
            "user_name": full_name,
            "week_number": selected_week,
            "question_id": q_item["id"],
            "pick": random.choice(["Yes", "No"]),
            "wager_amount": token_allocations[q_item["id"]]
        }).execute()

    return RedirectResponse(url=f"/bets?week={selected_week}&msg=Feeling+Lucky+Randomized", status_code=303)
