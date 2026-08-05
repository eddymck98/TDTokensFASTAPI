from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.database import get_supabase_client
from utils.dependencies import require_auth
from datetime import datetime, timezone

router = APIRouter(tags=["Admin"])
templates = Jinja2Templates(directory="templates")
supabase = get_supabase_client()

def require_admin(user=Depends(require_auth)):
    """Dependency forcing user to hold administrator status."""
    profile = supabase.table("profiles").select("is_admin").eq("id", user.id).single().execute().data
    if not profile or not profile.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user

@router.get("/admin", response_class=HTMLResponse)
async def admin_portal(request: Request, admin=Depends(require_admin)):
    """Renders the comprehensive system administration portal."""
    weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).execute()
    db_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else []
    
    return templates.TemplateResponse(request=request, name="admin_panel.html", context={
        "request": request,
        "available_weeks": db_weeks,
        "next_week": (db_weeks[-1] + 1) if db_weeks else 1
    })

@router.post("/admin/questions/publish")
async def publish_questions(
    request: Request,
    week_number: int = Form(...),
    admin=Depends(require_admin)
):
    """Publishes or updates the 10 weekly matchup questions."""
    form_data = await request.form()
    
    for i in range(1, 11):
        prompt = form_data.get(f"q{i}_prompt", "").strip()
        away = form_data.get(f"q{i}_away", "🏈 Free Agent / Neutral")
        home = form_data.get(f"q{i}_home", "🏈 Free Agent / Neutral")
        
        if prompt:
            combined_text = f"{prompt} | MATCHUP: {away} @ {home}"
            # Check if question exists
            existing = supabase.table("weekly_questions").select("id").eq("week_number", week_number).eq("question_number", i).execute().data
            if existing:
                supabase.table("weekly_questions").update({"question_text": combined_text}).eq("id", existing[0]["id"]).execute()
            else:
                supabase.table("weekly_questions").insert({
                    "week_number": week_number,
                    "question_number": i,
                    "question_text": combined_text,
                    "winning_answer": "Pending"
                }).execute()
                
    return RedirectResponse(url="/admin?success=questions_saved", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/admin/grade/live")
async def grade_week_live(
    request: Request,
    week_number: int = Form(...),
    admin=Depends(require_admin)
):
    """Grades matchup answers and recalculates player token banks instantly."""
    form_data = await request.form()
    
    for key, val in form_data.items():
        if key.startswith("win_ans_"):
            q_id = key.replace("win_ans_", "")
            supabase.table("weekly_questions").update({"winning_answer": val}).eq("id", q_id).execute()
            
    return RedirectResponse(url=f"/admin?success=graded_week_{week_number}", status_code=status.HTTP_303_SEE_OTHER)
