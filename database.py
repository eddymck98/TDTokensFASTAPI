import os
import streamlit as st
from supabase import Client, create_client

@st.cache_resource
def get_supabase_client() -> Client:
    """
    Initializes and returns a cached Supabase client using Streamlit secrets or environment variables.
    """
    url = os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "") or st.secrets.get("SUPABASE_KEY", "")
    return create_client(url, key)

supabase = get_supabase_client()

@st.cache_data(ttl=30)
def get_cached_profiles():
    """
    Retrieves and caches all user profile records from the Supabase profiles table.
    """
    try:
        res = supabase.table("profiles").select(
            "id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, "
            "selected_title, featured_badges, unlocked_badges, favorite_player, bio, default_league_view, "
            "email_notifications, high_contrast_mode, reduced_motion"
        ).execute()
        return res.data if res.data else []
    except Exception:
        return []

@st.cache_data(ttl=30)
def get_cached_weekly_questions(w_num: int):
    """
    Retrieves and caches weekly prediction scenarios for a specific week number.
    """
    try:
        res = supabase.table("weekly_questions").select("*").eq("week_number", w_num).order("question_number").execute()
        return res.data if res.data else []
    except Exception:
        return []

@st.cache_data(ttl=30)
def get_cached_all_weekly_questions_meta():
    """
    Retrieves question metadata across all active weeks, excluding system markers.
    """
    try:
        res = supabase.table("weekly_questions").select("week_number, question_number, winning_answer").neq(
            "week_number", 999
        ).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
        return res.data if res.data else []
    except Exception:
        return []

def get_true_global_token_balance(target_user_id: str) -> int:
    """
    Fetches the precise live token balance for a given user directly from Supabase.
    """
    try:
        data = supabase.table("profiles").select("tokens").eq("id", target_user_id).single().execute().data
        return max(0, (data or {}).get("tokens", 10))
    except Exception:
        return 10

def recalculate_all_user_balances(supabase_client: Client):
    """
    Recalculates and updates cumulative token balances for every user across all historical bets and touchdown rewards.
    """
    try:
        all_profiles = supabase_client.table("profiles").select("id").execute().data
        if not all_profiles:
            return
        for prof in all_profiles:
            uid = prof["id"]
            u_bets = supabase_client.table("user_bets").select("week_number, wager_amount, pick, weekly_questions(winning_answer)").eq("user_id", uid).execute().data
            u_td = supabase_client.table("touchdown_picks").select("week_number, is_correct").eq("user_id", uid).eq("is_correct", True).execute().data
            td_wins_map = {td["week_number"]: 5 for td in u_td}
            curr_tokens = 10
            
            if u_bets or td_wins_map:
                weeks_to_process = sorted(list(set([b["week_number"] for b in u_bets] + list(td_wins_map.keys()))))
                for w in weeks_to_process:
                    week_bets_list = [b for b in u_bets if b["week_number"] == w]
                    for b in week_bets_list:
                        w_ans = b.get("weekly_questions", {}).get("winning_answer")
                        if w_ans in ["Yes", "No"]:
                            if b["pick"] == w_ans:
                                curr_tokens += b["wager_amount"]
                            else:
                                curr_tokens -= b["wager_amount"]
                    if w in td_wins_map:
                        curr_tokens += 5
                        
            supabase_client.table("profiles").update({"tokens": max(0, curr_tokens)}).eq("id", uid).execute()
    except Exception:
        pass
