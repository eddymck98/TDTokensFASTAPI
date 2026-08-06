from datetime import datetime, timezone
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from utils.database import supabase
from utils.dependencies import get_current_user
from utils.helpers import NFL_TEAM_DATA, contains_profanity

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="templates")

NFL_TEAMS = list(NFL_TEAM_DATA.keys())

DEFAULT_QUESTION_TEMPLATES = [
    "Will QB 1 throw for over 250+ passing yards?",
    "Will RB 1 rush for 75+ rushing yards?",
    "Will WR 1 catch 6 or more receptions?",
    "Will Away Team score a touchdown in the 1st quarter?",
    "Will there be a successful 50+ yard Field Goal kicked?",
    "Will this game have over 45.5 combined points scored?",
    "Will any Defense record a pick-six or fumble recovery touchdown?",
    "Will TE 1 score a rushing or receiving touchdown?",
    "Will this game go into Overtime?",
    "Will Home Team record 3 or more sacks?"
]

def recalculate_all_user_balances():
    """Exact token recalculation engine from app.py."""
    try:
        all_profiles = supabase.table("profiles").select("id").execute().data
        if not all_profiles:
            return
        for prof in all_profiles:
            uid = prof["id"]
            u_bets = supabase.table("user_bets").select(
                "week_number, wager_amount, pick, weekly_questions(winning_answer)"
            ).eq("user_id", uid).execute().data
            
            u_td = supabase.table("touchdown_picks").select(
                "week_number, is_correct"
            ).eq("user_id", uid).eq("is_correct", True).execute().data
            
            td_wins_map = {td["week_number"]: 5 for td in u_td} if u_td else {}
            curr_tokens = 10
            
            if u_bets or td_wins_map:
                all_weeks = sorted(list(set([b["week_number"] for b in u_bets] + list(td_wins_map.keys()))))
                for w in all_weeks:
                    for b in [b for b in u_bets if b["week_number"] == w]:
                        w_ans = b.get("weekly_questions", {}).get("winning_answer") if b.get("weekly_questions") else None
                        if w_ans in ["Yes", "No"]:
                            curr_tokens += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
                    if w in td_wins_map:
                        curr_tokens += 5
            supabase.table("profiles").update({"tokens": max(0, curr_tokens)}).eq("id", uid).execute()
    except Exception as e:
        print(f"Error recalculating balances: {e}")


@router.get("/", response_class=HTMLResponse)
async def view_admin_panel(
    request: Request,
    manage_week: Optional[int] = None,
    grade_week: Optional[int] = None,
    active_tab: str = "Manage Questions",
    load_templates: bool = False,
    user_auth: dict = Depends(get_current_user)
):
    """Renders the comprehensive 8-module Admin Dashboard matching app.py exactly."""
    if not user_auth.get("is_admin"):
        raise HTTPException(status_code=403, detail="Super Admin access required")

    user_id = user_auth["id"]
    profile_res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = profile_res.data if profile_res and profile_res.data else {}

    # Calculate active token display (deducting active un-graded wagers)
    true_global_tokens = max(0, profile.get("tokens", 10))
    active_tokens_display = true_global_tokens

    weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
    db_weeks = sorted(list(set([r["week_number"] for r in weeks_res]))) if weeks_res else []

    if db_weeks:
        latest_w_active = db_weeks[-1]
        latest_week_status = supabase.table("weekly_questions").select("winning_answer").eq("week_number", latest_w_active).eq("question_number", 96).execute().data
        is_latest_graded = latest_week_status and latest_week_status[0]["winning_answer"] == "CLOSED"
        if not is_latest_graded:
            user_active_bets = supabase.table("user_bets").select("wager_amount, weekly_questions(winning_answer)").eq("user_id", user_id).eq("week_number", latest_w_active).execute().data
            if user_active_bets:
                total_wagered_active = sum(b["wager_amount"] for b in user_active_bets if b.get("weekly_questions", {}).get("winning_answer", "Pending") not in ["Yes", "No"])
                active_tokens_display = max(0, true_global_tokens - total_wagered_active)

    # Week Options for Management & Grading
    next_suggested_week = (db_weeks[-1] + 1) if db_weeks else 1
    manage_week_options = db_weeks + [next_suggested_week] if next_suggested_week not in db_weeks else db_weeks
    selected_m_week = manage_week or (db_weeks[-1] if db_weeks else 1)
    selected_g_week = grade_week or (db_weeks[-1] if db_weeks else 1)

    # 1. Manage Questions Data
    existing_qs_res = supabase.table("weekly_questions").select("*").eq("week_number", selected_m_week).order("question_number").execute().data
    existing_qs = [q for q in existing_qs_res if q.get("question_number", 0) <= 10] if existing_qs_res else []

    questions_form = []
    for i in range(1, 11):
        q_match = next((q for q in existing_qs if q.get("question_number") == i), None)
        if load_templates:
            prompt = DEFAULT_QUESTION_TEMPLATES[i-1]
            away = "🏈 Free Agent / Neutral"
            home = "🏈 Free Agent / Neutral"
        else:
            raw_txt = q_match["question_text"] if q_match else ""
            prompt = raw_txt.split(" | MATCHUP: ")[0] if " | MATCHUP: " in raw_txt else raw_txt
            away = "🏈 Free Agent / Neutral"
            home = "🏈 Free Agent / Neutral"
            if " | MATCHUP: " in raw_txt:
                parts = raw_txt.split(" | MATCHUP: ")[1].split(" @ ")
                if len(parts) == 2:
                    away = parts[0] if parts[0] in NFL_TEAMS else away
                    home = parts[1] if parts[1] in NFL_TEAMS else home

        questions_form.append({"number": i, "id": q_match["id"] if q_match else None, "prompt": prompt, "away": away, "home": home})

    # 2. Lockout Scheduler Data
    lock_row = supabase.table("weekly_questions").select("winning_answer").eq("week_number", selected_m_week).ilike("winning_answer", "LOCKTIME:%").execute().data
    current_locktime = lock_row[0]["winning_answer"].replace("LOCKTIME:", "") if lock_row else None

    # 3. Grade Week Data
    grade_qs_res = supabase.table("weekly_questions").select("*").eq("week_number", selected_g_week).order("question_number").execute().data
    grade_qs = [q for q in grade_qs_res if q.get("question_number", 0) <= 10 and not q.get("winning_answer", "").startswith("LOCKTIME:")] if grade_qs_res else []
    grade_tds = supabase.table("touchdown_picks").select("*").eq("week_number", selected_g_week).execute().data or []

    # 4. Bulk Token Adjuster Data
    profiles_list = supabase.table("profiles").select("id, full_name, tokens").order("full_name").execute().data or []

    # 8. Access Controls Data
    signin_lock_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 998).execute().data
    is_signin_locked = signin_lock_res[0]["winning_answer"] == "LOCKED" if signin_lock_res else False
    signup_lock_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 997).execute().data
    is_signup_locked = signup_lock_res[0]["winning_answer"] == "LOCKED" if signup_lock_res else False

    return templates.TemplateResponse("admin_panel.html", {
        "request": request,
        "profile": profile,
        "active_tokens": active_tokens_display,
        "true_tokens": true_global_tokens,
        "db_weeks": db_weeks,
        "manage_week_options": manage_week_options,
        "selected_m_week": selected_m_week,
        "selected_g_week": selected_g_week,
        "questions_form": questions_form,
        "current_locktime": current_locktime,
        "grade_qs": grade_qs,
        "grade_tds": grade_tds,
        "profiles": profiles_list,
        "nfl_teams": NFL_TEAMS,
        "is_signin_locked": is_signin_locked,
        "is_signup_locked": is_signup_locked,
        "active_tab": active_tab,
        "msg": request.query_params.get("msg")
    })


# ==========================================
# 1. MANAGE QUESTIONS ENDPOINTS
# ==========================================
@router.post("/questions/publish")
async def publish_questions(request: Request, week_number: int = Form(...)):
    form_data = await request.form()
    for i in range(1, 11):
        prompt = form_data.get(f"prompt_{i}", "").strip()
        away = form_data.get(f"away_{i}", "🏈 Free Agent / Neutral")
        home = form_data.get(f"home_{i}", "🏈 Free Agent / Neutral")
        q_id = form_data.get(f"id_{i}")

        if contains_profanity(prompt):
            raise HTTPException(status_code=400, detail="Restricted language detected in question prompt.")

        combined_text = f"{prompt} | MATCHUP: {away} @ {home}"
        if q_id and q_id != "None":
            supabase.table("weekly_questions").update({"question_text": combined_text}).eq("id", q_id).execute()
        else:
            supabase.table("weekly_questions").insert({
                "week_number": week_number, "question_number": i, "question_text": combined_text, "winning_answer": "Pending"
            }).execute()

    return RedirectResponse(url=f"/admin?manage_week={week_number}&active_tab=Manage Questions&msg=Questions+Published+Successfully", status_code=303)


@router.post("/questions/clear")
async def clear_week(week_number: int = Form(...)):
    supabase.table("weekly_questions").delete().eq("week_number", week_number).eq("winning_answer", "Pending").execute()
    return RedirectResponse(url=f"/admin?manage_week={week_number}&active_tab=Manage Questions&msg=Week+Cleared", status_code=303)


# ==========================================
# 2. AUTO-LOCKOUT SCHEDULER ENDPOINTS
# ==========================================
@router.post("/lockout/save")
async def save_lockout(week_number: int = Form(...), lock_date: str = Form(...), lock_time: str = Form(...)):
    iso_dt = f"{lock_date}T{lock_time}:00+00:00"
    supabase.table("weekly_questions").delete().eq("week_number", week_number).ilike("winning_answer", "LOCKTIME:%").execute()
    supabase.table("weekly_questions").insert({
        "week_number": week_number, "question_number": 99, "question_text": "LOCKTIME SCHEDULER", "winning_answer": f"LOCKTIME:{iso_dt}"
    }).execute()
    return RedirectResponse(url=f"/admin?manage_week={week_number}&active_tab=Auto-Lockout Scheduler&msg=Lockout+Scheduled", status_code=303)


@router.post("/lockout/clear")
async def clear_lockout(week_number: int = Form(...)):
    supabase.table("weekly_questions").delete().eq("week_number", week_number).ilike("winning_answer", "LOCKTIME:%").execute()
    return RedirectResponse(url=f"/admin?manage_week={week_number}&active_tab=Auto-Lockout Scheduler&msg=Lockout+Cleared", status_code=303)


# ==========================================
# 3. LIVE GAME GRADING & TOKEN CALCULATOR
# ==========================================
@router.post("/grade/save")
async def save_live_grading(request: Request, week_number: int = Form(...)):
    form_data = await request.form()
    for key, val in form_data.items():
        if key.startswith("q_ans_"):
            q_id = key.replace("q_ans_", "")
            supabase.table("weekly_questions").update({"winning_answer": val}).eq("id", q_id).execute()
        elif key.startswith("td_ans_"):
            td_id = key.replace("td_ans_", "")
            is_correct = True if val == "Correct" else (False if val == "Incorrect" else None)
            supabase.table("touchdown_picks").update({"is_correct": is_correct}).eq("id", td_id).execute()

    recalculate_all_user_balances()
    return RedirectResponse(url=f"/admin?grade_week={week_number}&active_tab=Grade Week & Calculate Points&msg=Results+Saved+And+Tokens+Recalculated", status_code=303)


@router.post("/grade/close_week")
async def close_week(week_number: int = Form(...)):
    supabase.table("weekly_questions").delete().eq("week_number", week_number).eq("question_number", 96).execute()
    supabase.table("weekly_questions").insert({
        "week_number": week_number, "question_number": 96, "question_text": "WEEKLY CLOSED MARKER", "winning_answer": "CLOSED"
    }).execute()
    return RedirectResponse(url=f"/admin?grade_week={week_number}&active_tab=Grade Week & Calculate Points&msg=Week+Closed", status_code=303)


# ==========================================
# 4. BULK TOKEN ADJUSTER
# ==========================================
@router.post("/tokens/adjust")
async def adjust_player_tokens(user_id: str = Form(...), action: str = Form(...), amount: int = Form(...)):
    prof_res = supabase.table("profiles").select("tokens").eq("id", user_id).single().execute().data
    if prof_res:
        curr = prof_res.get("tokens", 10)
        new_val = curr + amount if action == "add" else (max(0, curr - amount) if action == "subtract" else amount)
        supabase.table("profiles").update({"tokens": new_val}).eq("id", user_id).execute()
    return RedirectResponse(url="/admin?active_tab=Bulk Token Adjuster&msg=Tokens+Adjusted", status_code=303)


# ==========================================
# 5. EXPORT LEAGUE DATA (CSV)
# ==========================================
@router.get("/export_csv")
async def export_csv():
    profiles_res = supabase.table("profiles").select("id, full_name, tokens, favorite_team, selected_title").order("tokens", desc=True).execute().data or []
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["User ID", "Full Name", "Tokens", "Favorite Team", "Selected Title"])
    writer.writeheader()
    for p in profiles_res:
        writer.writerow({
            "User ID": p["id"], "Full Name": p["full_name"], "Tokens": p.get("tokens", 10),
            "Favorite Team": p.get("favorite_team", "N/A"), "Selected Title": p.get("selected_title", "N/A")
        })
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=touchdown_tokens_standings.csv"})


# ==========================================
# 6. LEAGUE CHAT ANNOUNCEMENT
# ==========================================
@router.post("/announcement/broadcast")
async def broadcast_announcement(message: str = Form(...), admin_user_id: str = Form("admin")):
    if contains_profanity(message):
        raise HTTPException(status_code=400, detail="Restricted language detected.")
    formatted_msg = f"🚨 **COMMISSIONER ANNOUNCEMENT:** {message.strip()}"
    supabase.table("trash_talk").insert({
        "user_id": admin_user_id, "message": formatted_msg, "league_id": "00000000-0000-0000-0000-000000000001"
    }).execute()
    return RedirectResponse(url="/admin?active_tab=League Chat Announcement&msg=Announcement+Broadcasted", status_code=303)


# ==========================================
# 7. ARCHIVE & RESET SEASON
# ==========================================
@router.post("/season/archive_reset")
async def archive_and_reset_season(season_label: str = Form(...)):
    profiles_res = supabase.table("profiles").select("*").order("tokens", desc=True).execute().data or []
    if profiles_res:
        champ_id = profiles_res[0]["id"]
        champ_prof = supabase.table("profiles").select("unlocked_badges").eq("id", champ_id).single().execute().data
        if champ_prof:
            unlocked = champ_prof.get("unlocked_badges") or []
            if "🏆 League Champion" not in unlocked:
                unlocked.append("🏆 League Champion")
                supabase.table("profiles").update({"unlocked_badges": unlocked, "selected_title": "👑 League Champion"}).eq("id", champ_id).execute()

        supabase.table("archived_seasons").insert({
            "league_id": "00000000-0000-0000-0000-000000000001", "season_label": season_label.strip(), "standings_json": profiles_res
        }).execute()

        for p in profiles_res:
            supabase.table("profiles").update({"tokens": 10}).eq("id", p["id"]).execute()

    return RedirectResponse(url="/admin?active_tab=Archive & Reset Season&msg=Season+Archived+and+Tokens+Reset", status_code=303)


# ==========================================
# 8. APP ACCESS CONTROL
# ==========================================
@router.post("/access/toggle")
async def toggle_access_control(lock_signin: Optional[str] = Form(None), lock_signup: Optional[str] = Form(None)):
    supabase.table("weekly_questions").delete().eq("week_number", 998).execute()
    supabase.table("weekly_questions").insert({
        "week_number": 998, "question_number": 99, "question_text": "SIGNIN LOCK SETTING", "winning_answer": "LOCKED" if lock_signin == "on" else "UNLOCKED"
    }).execute()

    supabase.table("weekly_questions").delete().eq("week_number", 997).execute()
    supabase.table("weekly_questions").insert({
        "week_number": 997, "question_number": 99, "question_text": "SIGNUP LOCK SETTING", "winning_answer": "LOCKED" if lock_signup == "on" else "UNLOCKED"
    }).execute()

    return RedirectResponse(url="/admin?active_tab=App Access Control&msg=Access+Controls+Updated", status_code=303)
