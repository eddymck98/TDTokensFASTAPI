import os
import streamlit as st
from supabase import Client
from dependencies import NFL_TEAM_DATA, AVAILABLE_TITLES
from badges_logic import sync_and_get_user_badges

def get_earned_title(supabase: Client, target_user_id: str) -> str:
    """
    Retrieves the user's active custom selected title or computes their highest earned prestigious title.
    """
    try:
        prof_res = supabase.table("profiles").select("selected_title").eq("id", target_user_id).single().execute().data
        if prof_res and prof_res.get("selected_title") in AVAILABLE_TITLES:
            return prof_res.get("selected_title")
    except Exception:
        pass
        
    user_badges = sync_and_get_user_badges(supabase, target_user_id)
    for title, info in AVAILABLE_TITLES.items():
        if info["badge"] and info["badge"] in user_badges:
            return title
    return "🏈 Gridiron Contender"

def calculate_nemesis(supabase: Client, target_user_id: str, allowed_peer_ids=None) -> tuple:
    """
    Calculates the user's 'Nemesis' — the league rival whom they disagreed with the most
    on weekly bets where the rival ended up winning points at the user's expense.
    """
    try:
        user_bets = supabase.table("user_bets").select("week_number, question_id, pick").eq("user_id", target_user_id).execute().data
        if not user_bets:
            return "None Yet", 0
            
        user_picks_map = {(b["week_number"], b["question_id"]): b["pick"] for b in user_bets}
        rival_disagreements = {}

        for (w_num, q_id), u_pick in user_picks_map.items():
            other_bets_query = supabase.table("user_bets").select("user_id, pick, weekly_questions(winning_answer)").eq("week_number", w_num).eq("question_id", q_id).neq("user_id", target_user_id)
            if allowed_peer_ids is not None:
                if not allowed_peer_ids:
                    continue
                other_bets_query = other_bets_query.in_("user_id", list(allowed_peer_ids))
            other_bets = other_bets_query.execute().data
            
            if other_bets:
                for ob in other_bets:
                    rival_id, rival_pick, winning_ans = ob["user_id"], ob["pick"], ob.get("weekly_questions", {}).get("winning_answer")
                    if rival_pick != u_pick and winning_ans in ["Yes", "No"] and rival_pick == winning_ans:
                        rival_disagreements[rival_id] = rival_disagreements.get(rival_id, 0) + 1

        if not rival_disagreements:
            return "None Yet", 0
            
        nemesis_id = max(rival_disagreements, key=rival_disagreements.get)
        nemesis_prof = supabase.table("profiles").select("full_name").eq("id", nemesis_id).single().execute().data
        return nemesis_prof.get("full_name", "Unknown Rival") if nemesis_prof else "Unknown Rival", rival_disagreements[nemesis_id]
    except Exception:
        return "None Yet", 0

def calculate_streak(supabase: Client, target_user_id: str) -> str:
    """
    Calculates the user's current consecutive winning streak across graded weekly questions.
    """
    try:
        u_bets = supabase.table("user_bets").select("week_number, pick, weekly_questions(winning_answer)").eq("user_id", target_user_id).order("week_number", desc=True).execute().data
        if not u_bets:
            return "0W"
            
        streak = 0
        for b in u_bets:
            w_ans = b.get("weekly_questions", {}).get("winning_answer")
            if w_ans in ["Yes", "No"]:
                if b["pick"] == w_ans:
                    streak += 1
                else:
                    break
        return f"{streak}W" if streak > 0 else "0W"
    except Exception:
        return "0W"
