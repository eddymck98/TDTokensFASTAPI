import os
from datetime import datetime, timezone
from typing import List, Tuple, Set, Optional
from supabase import Client

PROFANITY_FILTER = ["damn", "hell", "crap", "shit", "fuck", "bitch", "asshole", "dick", "cunt", "bastard"]

AVAILABLE_TITLES = {
    "🏈 Gridiron Contender": {"badge": None, "req": "Default baseline title for all players."},
    "👑 League Champion": {"badge": "🏆 League Champion", "req": "Be crowned the official end-of-season League Champion."},
    "⭐ League Commissioner": {"badge": "⭐ League Commissioner", "req": "Create or administer a custom mini-league."},
    "🔮 The Oracle": {"badge": "🔮 Oracle of Delphi", "req": "Successfully call a 5+ token wager correctly 4 weeks in a row."},
    "💰 Token Tycoon": {"badge": "🚀 Token Tycoon", "req": "Accumulate 50+ lifetime tokens earned."},
    "⚡ Gridiron Prophet": {"badge": "⚡ Gridiron Prophet", "req": "Correctly predict 13+ Touchdown Scorers across the season."},
    "🎯 Sharp Shooter": {"badge": "🎯 Sniper", "req": "Correctly predict 9+ Touchdown Scorers across the season."},
    "🏈 TD Specialist": {"badge": "🏈 TD Guru", "req": "Correctly predict 5+ Touchdown Scorers."},
    "🛡️ Mini-League Monarch": {"badge": "🛡️ Mini-League Monarch", "req": "Finish in 1st place in any active mini-league."},
    "📉 Bankrupt Gambler": {"badge": "📉 Down Bad", "req": "Reach a token balance of 0 tokens."}
}

MASTER_BADGES = {
    "🚀 Token Tycoon": "Accumulate 50+ lifetime tokens earned across your career",
    "🎯 High Roller": "Wager 10+ tokens on a single question",
    "⚡ Double Down Legend": "Wager 15+ total tokens in a single week",
    "💣 All-In Maverick": "Wager 100% of your remaining token balance on a slate",
    "🏈 TD Guru": "Correctly predict 5+ Touchdown Scorers",
    "🎯 Sniper": "Correctly predict 9+ Touchdown Scorers across the season",
    "👑 Weekly High Scorer": "Win the most net tokens in a single week",
    "🎯 Perfect 10/10": "Correctly answer all 10 scenarios in a single week",
    "🧊 Clutch Gene": "Win a scenario where 75%+ of the league picked the wrong side",
    "🛡️ Iron Defender": "Submit bets for 5 or more weeks without missing",
    "💰 Century Club": "Accumulate 100+ total cumulative tokens won across history",
    "📉 Wall Street Bets": "Take the largest token loss in a single week",
    "📉 Down Bad": "Reach a token balance of 0 tokens",
    "🏆 League Champion": "Be crowned the official end-of-season League Champion",
    "⭐ League Commissioner": "Create or administer a custom mini-league",
    "🔮 Oracle of Delphi": "Successfully call a 5+ token wager correctly 4 weeks in a row",
    "🔥 Untouchable Run": "Gain 20+ net tokens in a single weekly slate",
    "⚡ Gridiron Prophet": "Correctly predict 13+ Touchdown Scorers across the season",
    "💎 Diamond Hands": "Survive with fewer than 3 tokens remaining and bounce back to 30+",
    "🛡️ Mini-League Monarch": "Finish 1st place in any active mini-league standing",
    "🌟 Gridiron General": "Maintain a 70%+ win rate across 20+ total bets in your mini-league",
    "🎯 Pick Six Prodigy": "Correctly predict a Touchdown Scorer on 3 consecutive weeks",
    "🎩 Commissioner's Right Hand": "Be an active member of 3+ custom mini-leagues"
}

def get_true_global_token_balance(target_user_id: str, supabase: Client) -> int:
    """Calculates the verified global token balance directly from the database."""
    try:
        res = supabase.table("profiles").select("tokens").eq("id", target_user_id).single().execute()
        return max(0, (res.data or {}).get("tokens", 10))
    except Exception:
        return 10

def calculate_nemesis(target_user_id: str, supabase: Client, allowed_peer_ids: Optional[Set[str]] = None) -> Tuple[str, int]:
    """Calculates the user's biggest rival (Nemesis) based on contested weekly picks."""
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
                    rival_id = ob["user_id"]
                    rival_pick = ob["pick"]
                    wq = ob.get("weekly_questions")
                    winning_ans = wq.get("winning_answer") if isinstance(wq, dict) else None
                    
                    if rival_pick != u_pick and winning_ans in ["Yes", "No"] and rival_pick == winning_ans:
                        rival_disagreements[rival_id] = rival_disagreements.get(rival_id, 0) + 1

        if not rival_disagreements:
            return "None Yet", 0
        
        nemesis_id = max(rival_disagreements, key=rival_disagreements.get)
        nemesis_prof = supabase.table("profiles").select("full_name").eq("id", nemesis_id).single().execute().data
        return nemesis_prof.get("full_name", "Unknown Rival") if nemesis_prof else "Unknown Rival", rival_disagreements[nemesis_id]
    except Exception:
        return "None Yet", 0

def calculate_streak(target_user_id: str, supabase: Client) -> str:
    """Calculates the user's active correct prediction streak."""
    try:
        u_bets = supabase.table("user_bets").select("week_number, pick, weekly_questions(winning_answer)").eq("user_id", target_user_id).order("week_number", desc=True).execute().data
        if not u_bets:
            return "0W"
        
        streak = 0
        for b in u_bets:
            wq = b.get("weekly_questions")
            w_ans = wq.get("winning_answer") if isinstance(wq, dict) else None
            if w_ans in ["Yes", "No"]:
                if b["pick"] == w_ans:
                    streak += 1
                else:
                    break
        return f"{streak}W" if streak > 0 else "0W"
    except Exception:
        return "0W"

def sync_and_get_user_badges(target_user_id: str, supabase: Client) -> List[str]:
    """Evaluates user gameplay milestones and synchronizes unlocked badges in Supabase."""
    try:
        p_data = supabase.table("profiles").select("tokens, unlocked_badges, is_admin").eq("id", target_user_id).single().execute().data
        if not p_data:
            return []
    except Exception:
        return []

    toks = p_data.get("tokens", 10)
    existing_unlocked = p_data.get("unlocked_badges") if isinstance(p_data.get("unlocked_badges"), list) else []
    u_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", target_user_id).execute().data
    u_td = supabase.table("touchdown_picks").select("*").eq("user_id", target_user_id).eq("is_correct", True).order("week_number").execute().data

    newly_earned = set(existing_unlocked)
    
    # Commissioner & Admin badges
    if supabase.table("leagues").select("id").eq("created_by", target_user_id).execute().data or p_data.get("is_admin"):
        newly_earned.add("⭐ League Commissioner")
    
    if any(b.get("wager_amount", 0) >= 10 for b in u_bets):
        newly_earned.add("🎯 High Roller")
    
    if len(u_td) >= 5:
        newly_earned.add("🏈 TD Guru")
    if len(u_td) >= 9:
        newly_earned.add("🎯 Sniper")
    if len(u_td) >= 13:
        newly_earned.add("⚡ Gridiron Prophet")
    
    if toks == 0:
        newly_earned.add("📉 Down Bad")

    my_joined_leagues = supabase.table("league_members").select("league_id").eq("user_id", target_user_id).execute().data
    if my_joined_leagues and len(my_joined_leagues) >= 3:
        newly_earned.add("🎩 Commissioner's Right Hand")

    # Pick six consecutive touchdown scorer streaks
    if u_td:
        correct_weeks = sorted([td["week_number"] for td in u_td])
        consec_count, max_consec = 1, 1
        for i in range(1, len(correct_weeks)):
            if correct_weeks[i] == correct_weeks[i - 1] + 1:
                consec_count += 1
                max_consec = max(max_consec, consec_count)
            else:
                consec_count = 1
        if max_consec >= 3:
            newly_earned.add("🎯 Pick Six Prodigy")

    weeks_played = set()
    total_lifetime_won = 0
    weekly_nets = {}

    for b in u_bets:
        w_num = b["week_number"]
        wq = b.get("weekly_questions")
        w_ans = wq.get("winning_answer") if isinstance(wq, dict) else None
        wager = b.get("wager_amount", 0)
        
        weeks_played.add(w_num)
        if w_num not in weekly_nets:
            weekly_nets[w_num] = {"gains": 0, "losses": 0}
        
        if w_ans in ["Yes", "No"]:
            if b["pick"] == w_ans:
                total_lifetime_won += wager
                weekly_nets[w_num]["gains"] += wager
            else:
                weekly_nets[w_num]["losses"] += wager

    for td in u_td:
        if td["week_number"] in weekly_nets:
            weekly_nets[td["week_number"]]["gains"] += 5

    if total_lifetime_won >= 50:
        newly_earned.add("🚀 Token Tycoon")

    # Oracle streak calculation
    sorted_weeks = sorted(list(weekly_nets.keys()))
    consecutive_oracle_weeks = 0
    for w in sorted_weeks:
        week_bets = [b for b in u_bets if b["week_number"] == w]
        has_oracle_hit = False
        for b in week_bets:
            wq = b.get("weekly_questions")
            w_ans = wq.get("winning_answer") if isinstance(wq, dict) else None
            if b.get("wager_amount", 0) >= 5 and b["pick"] == w_ans:
                has_oracle_hit = True
                break
        
        if has_oracle_hit:
            consecutive_oracle_weeks += 1
            if consecutive_oracle_weeks >= 4:
                newly_earned.add("🔮 Oracle of Delphi")
        else:
            consecutive_oracle_weeks = 0

    for w, w_data in weekly_nets.items():
        if w_data["gains"] - w_data["losses"] >= 20:
            newly_earned.add("🔥 Untouchable Run")

    if toks >= 30:
        sim_tokens, ever_low = 10, False
        for w in sorted_weeks:
            if sim_tokens < 3:
                ever_low = True
            sim_tokens += weekly_nets[w]["gains"] - weekly_nets[w]["losses"]
        if ever_low:
            newly_earned.add("💎 Diamond Hands")

    if len(weeks_played) >= 5:
        newly_earned.add("🛡️ Iron Defender")
    if total_lifetime_won >= 100:
        newly_earned.add("💰 Century Club")

    final_badges_list = list(newly_earned)
    if set(final_badges_list) != set(existing_unlocked):
        try:
            supabase.table("profiles").update({"unlocked_badges": final_badges_list}).eq("id", target_user_id).execute()
        except Exception:
            pass

    return final_badges_list

def get_earned_title(target_user_id: str, supabase: Client) -> str:
    """Determines the active prestigious title unlocked by the user."""
    try:
        prof_res = supabase.table("profiles").select("selected_title").eq("id", target_user_id).single().execute().data
        if prof_res and prof_res.get("selected_title") in AVAILABLE_TITLES:
            return prof_res.get("selected_title")
    except Exception:
        pass
    
    user_badges = sync_and_get_user_badges(target_user_id, supabase)
    for title, info in AVAILABLE_TITLES.items():
        if info["badge"] and info["badge"] in user_badges:
            return title
    return "🏈 Gridiron Contender"
