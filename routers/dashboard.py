import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from database import NFL_TEAM_DATA

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard_root(request: Request):
    """Renders the dashboard explicitly when hitting /dashboard or root."""
    return await render_dashboard_or_index(request)

async def render_dashboard_or_index(request: Request):
    """Core logic to render either the dashboard (if logged in) or index (if logged out)."""
    session_cookie = request.cookies.get("td_tokens_session")
    templates = request.app.state.templates
    
    if not session_cookie:
        return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "team_data": NFL_TEAM_DATA})
    
    supabase = request.app.state.supabase
    
    try:
        token_data = json.loads(session_cookie)
        access_token = token_data.get("access_token")
        supabase.auth.set_session(access_token, token_data.get("refresh_token"))
        user = supabase.auth.get_user(access_token).user
        if not user:
            return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "team_data": NFL_TEAM_DATA})
    except Exception:
        return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "team_data": NFL_TEAM_DATA})

    # --- 1. ISOLATED PROFILE FETCH ---
    try:
        user_email = user.email
        profile_res = supabase.table("profiles").select("*").eq("email", user_email).execute()
        
        current_profile = profile_res.data[0] if profile_res.data else {
            "tokens": 10, 
            "full_name": user_email.split('@')[0],
            "selected_title": "🏈 Gridiron Contender",
            "favorite_team": "🏈 Free Agent / Neutral",
            "is_admin": False
        }
        active_tokens = current_profile.get("tokens", 10)
    except Exception as e:
        print(f"Profile Fetch Error: {e}")
        current_profile = {
            "tokens": 10, 
            "full_name": "Error Loading Profile",
            "selected_title": "🏈 Gridiron Contender",
            "favorite_team": "🏈 Free Agent / Neutral",
            "is_admin": False
        }
        active_tokens = 10

    # --- 2. ISOLATED BETS, CONSENSUS, STATS & GRAPH HISTORY FETCH ---
    available_weeks = []
    current_user_bets = []
    td_pick = None
    consensus_data = []
    personal_stats = {"total_bets": 0, "wins": 0, "losses": 0, "pending": 0, "tokens_wagered": 0}
    share_text = "🏈 Weekly Lock-Ins Loaded 🏈\n\nNo picks submitted yet."
    token_history_data = {"labels": [], "values": []}
    
    prediction_wins = 0
    prediction_total = 0
    td_wins = 0
    td_total = 0
    
    try:
        weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        if weeks_res.data:
            available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data])))
        
        if available_weeks:
            latest_week = available_weeks[-1]
            
            bets_res = supabase.table("user_bets").select("*").eq("user_id", user.id).eq("week_number", latest_week).execute()
            q_res = supabase.table("weekly_questions").select("*").eq("week_number", latest_week).execute()
            questions_map = {q["id"]: q for q in q_res.data} if q_res.data else {}
            
            if bets_res.data:
                for b in bets_res.data:
                    q_id = b.get("question_id")
                    wq = questions_map.get(q_id, {})
                    
                    b["question_number"] = wq.get("question_number", 99)
                    raw_text = wq.get("question_text", "Unknown Matchup")
                    b["question_text"] = raw_text.split(" | MATCHUP: ")[0] if " | MATCHUP: " in raw_text else raw_text
                    
                    w_ans = wq.get("winning_answer", "Pending")
                    if w_ans in ["Yes", "No"]:
                        b["status_label"] = "Won ✅" if b.get("pick") == w_ans else "Lost ❌"
                    else:
                        b["status_label"] = "Pending ⏳"
                        
                    current_user_bets.append(b)
                    
                    personal_stats["tokens_wagered"] += b.get("wager_amount", 0)
                    if "Won" in b["status_label"]:
                        personal_stats["wins"] += 1
                    elif "Lost" in b["status_label"]:
                        personal_stats["losses"] += 1
                    else:
                        personal_stats["pending"] += 1
                
                current_user_bets = sorted(current_user_bets, key=lambda x: int(x.get("question_number", 99)) if str(x.get("question_number")).isdigit() else 99)
                personal_stats["total_bets"] = len(current_user_bets)
                
                share_lines = [f"🏈 Weekly Lock-Ins (Week {latest_week}) 🏈\n"]
                for idx, b in enumerate(current_user_bets, start=1):
                    q_text = b.get('question_text', f"Question {idx}")
                    share_lines.append(f"{idx}. {q_text}: {b['pick']} ({b['wager_amount']} 🪙)")
                share_text = "\n".join(share_lines)
            
            td_res = supabase.table("touchdown_picks").select("*").eq("user_id", user.id).eq("week_number", latest_week).execute()
            if td_res.data:
                td_pick = td_res.data[0]
                td_status = td_pick.get("is_correct")
                if td_status is True:
                    td_pick["status_label"] = "Won ✅"
                    personal_stats["wins"] += 1
                elif td_status is False:
                    td_pick["status_label"] = "Lost ❌"
                    personal_stats["losses"] += 1
                else:
                    td_pick["status_label"] = "Pending ⏳"
                    personal_stats["pending"] += 1
                
                share_text += f"\n\nTD Bonus: {td_pick.get('player_name', '')}"

            all_bets = supabase.table("user_bets").select("question_id, pick, wager_amount").eq("week_number", latest_week).execute()
            if all_bets.data:
                q_stats = {}
                for b in all_bets.data:
                    qid = b["question_id"]
                    
                    if qid not in q_stats:
                        raw_q_text = questions_map.get(qid, {}).get("question_text", "")
                        q_text = raw_q_text.split(" | MATCHUP: ")[0] if " | MATCHUP: " in raw_q_text else raw_q_text
                        
                        q_stats[qid] = {
                            "yes_count": 0, "no_count": 0, "total_wager": 0, 
                            "q_num": questions_map.get(qid, {}).get("question_number", 99), 
                            "text": q_text
                        }
                    
                    if b["pick"] == "Yes":
                        q_stats[qid]["yes_count"] += 1
                    elif b["pick"] == "No":
                        q_stats[qid]["no_count"] += 1
                        
                    q_stats[qid]["total_wager"] += b.get("wager_amount", 0)
                
                for qid, stats in q_stats.items():
                    total_picks = stats["yes_count"] + stats["no_count"]
                    if total_picks > 0:
                        stats["yes_pct"] = int((stats["yes_count"] / total_picks) * 100)
                        stats["no_pct"] = int((stats["no_count"] / total_picks) * 100)
                    else:
                        stats["yes_pct"], stats["no_pct"] = 0, 0
                    consensus_data.append(stats)
                
                consensus_data = sorted(consensus_data, key=lambda x: x.get("total_wager", 0), reverse=True)[:3]
                consensus_data = sorted(consensus_data, key=lambda x: int(x["q_num"]) if str(x["q_num"]).isdigit() else 99)

        graph_labels = []
        graph_values = []
        running_tokens = 10  
        
        all_user_matchup_bets = supabase.table("user_bets").select("question_id, pick, wager_amount, week_number").eq("user_id", user.id).execute().data or []
        won_matchup_count = 0
        played_matchup_count = 0

        all_user_td_picks = supabase.table("touchdown_picks").select("is_correct, week_number").eq("user_id", user.id).execute().data or []
        won_td_count = 0
        played_td_count = 0

        for w in available_weeks:
            try:
                status_res = supabase.table("weekly_questions").select("winning_answer").eq("week_number", w).eq("question_number", 98).execute()
                is_closed = status_res.data and status_res.data[0].get("winning_answer") == "CLOSED"
                
                week_bets = [b for b in all_user_matchup_bets if b.get("week_number") == w]
                week_qs = {q["id"]: q.get("winning_answer") for q in supabase.table("weekly_questions").select("id, winning_answer").eq("week_number", w).execute().data}
                
                week_delta = 0
                if week_bets:
                    for wb in week_bets:
                        wager = wb.get("wager_amount", 0)
                        pick = wb.get("pick")
                        winning_ans = week_qs.get(wb.get("question_id"))
                        
                        if winning_ans in ["Yes", "No"]:
                            played_matchup_count += 1
                            if pick == winning_ans:
                                week_delta += wager
                                won_matchup_count += 1
                            else:
                                week_delta -= wager
                
                td_record = [t for t in all_user_td_picks if t.get("week_number") == w]
                if td_record:
                    td_status = td_record[0].get("is_correct")
                    if td_status is True or td_status is False:
                        played_td_count += 1
                        if td_status is True:
                            week_delta += 5
                            won_td_count += 1

                if is_closed:
                    running_tokens += week_delta
                    graph_labels.append(f"Week {w}")
                    graph_values.append(running_tokens)
            except Exception as graph_err:
                print(f"Error computing graph for week {w}: {graph_err}")
                
        token_history_data = {"labels": graph_labels, "values": graph_values}

        # Season Running Totals assignment
        prediction_wins = won_matchup_count
        prediction_total = played_matchup_count

        td_wins = won_td_count
        td_total = played_td_count

    except Exception as e:
        print(f"Bets Fetch Error: {e}")

    # --- 3. RECENT MINI-LEAGUE ACTIVITY FEED FETCH (SAFE PAYOUTS ONLY) ---
    recent_league_activity = []
    try:
        # A. Find all mini-leagues the current user belongs to
        my_leagues_res = supabase.table("league_members").select("league_id, leagues(name)").eq("user_id", user.id).execute()
        my_league_ids = [m["league_id"] for m in my_leagues_res.data] if my_leagues_res.data else []
        
        if my_league_ids:
            # B. Find other user IDs who share these same mini-leagues
            shared_members_res = supabase.table("league_members").select("user_id").in_("league_id", my_league_ids).execute()
            shared_user_ids = list(set([m["user_id"] for m in shared_members_res.data])) if shared_members_res.data else []
            
            # C. Fetch ONLY token payouts/wins from shared users (NO specific pick/question details leaked)
            if shared_user_ids:
                payouts_res = supabase.table("user_bets") \
                    .select("user_id, tokens_awarded, week_number, profiles(full_name)") \
                    .in_("user_id", shared_user_ids) \
                    .gt("tokens_awarded", 0) \
                    .order("created_at", desc=True) \
                    .limit(8) \
                    .execute()
                    
                if payouts_res.data:
                    for p in payouts_res.data:
                        p_info = p.get("profiles") or {}
                        recent_league_activity.append({
                            "user_name": p_info.get("full_name", "A rival player"),
                            "tokens_won": p.get("tokens_awarded", 0),
                            "week_number": p.get("week_number", 1)
                        })
    except Exception as e:
        print(f"Activity Feed Error: {e}")

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "request": request,
            "profile": current_profile,
            "active_tokens": active_tokens,
            "available_weeks": available_weeks,
            "current_user_bets": current_user_bets,
            "td_pick": td_pick,
            "personal_stats": personal_stats,
            "consensus_data": consensus_data,
            "share_text": share_text,
            "token_history_json": json.dumps(token_history_data),
            "prediction_wins": prediction_wins,
            "prediction_total": prediction_total,
            "td_wins": td_wins,
            "td_total": td_total,
            "recent_league_activity": recent_league_activity,
            "team_data": NFL_TEAM_DATA
        }
    )
