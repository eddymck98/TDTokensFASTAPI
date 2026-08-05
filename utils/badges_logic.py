from utils.database import get_supabase_client

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

def sync_and_get_user_badges(target_user_id: str) -> list:
    """Evaluates and awards badges for a specific user based on their betting history."""
    supabase = get_supabase_client()
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
    
    # Core logical triggers
    if supabase.table("leagues").select("id").eq("created_by", target_user_id).execute().data or p_data.get("is_admin"): newly_earned.add("⭐ League Commissioner")
    if u_bets and any(b["wager_amount"] >= 10 for b in u_bets): newly_earned.add("🎯 High Roller")
    if u_td and len(u_td) >= 5: newly_earned.add("🏈 TD Guru")
    if u_td and len(u_td) >= 9: newly_earned.add("🎯 Sniper")
    if u_td and len(u_td) >= 13: newly_earned.add("⚡ Gridiron Prophet")
    if toks == 0: newly_earned.add("📉 Down Bad")

    # Sync updates back to the database if new badges were earned
    final_badges_list = list(newly_earned)
    if set(final_badges_list) != set(existing_unlocked):
        try: 
            supabase.table("profiles").update({"unlocked_badges": final_badges_list}).eq("id", target_user_id).execute()
        except Exception: 
            pass

    return final_badges_list
