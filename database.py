import os
import random
import resend
from datetime import datetime, timezone
from typing import List, Tuple, Set, Optional
from supabase import Client

# ==========================================
# ENVIRONMENT & RESEND CONFIGURATION
# ==========================================

resend.api_key = os.environ.get("RESEND_API_KEY", "")

PROFANITY_FILTER = [
    "damn", "hell", "crap", "shit", "fuck", "bitch", 
    "asshole", "dick", "cunt", "bastard"
]

def contains_profanity(text: str) -> bool:
    """Checks if text contains any restricted words from the profanity filter."""
    if not text:
        return False
    text_lower = text.lower()
    words = text_lower.split()
    for p_word in PROFANITY_FILTER:
        if p_word in text_lower or any(p_word == w for w in words):
            return True
    return False


# ==========================================
# STATIC DATA & NFL CONFIGURATIONS
# ==========================================

# Universal verified American football stadium background for all teams
UNIFIED_STADIUM_BG = "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"

NFL_TEAM_DATA = {
    "🏈 Free Agent / Neutral": {"logo": "...", "color": "#fbbf24", "stadium": UNIFIED_STADIUM_BG},
    "🃏 Arizona Cardinals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png", "color": "#97233F", "stadium": UNIFIED_STADIUM_BG},
    "🦅 Atlanta Falcons": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png", "color": "#A71930", "stadium": UNIFIED_STADIUM_BG},
    "🐦‍⬛ Baltimore Ravens": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png", "color": "#241773", "stadium": UNIFIED_STADIUM_BG},
    "🦬 Buffalo Bills": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png", "color": "#00338D", "stadium": UNIFIED_STADIUM_BG},
    "🐾 Carolina Panthers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png", "color": "#0085CA", "stadium": UNIFIED_STADIUM_BG},
    "🐻 Chicago Bears": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png", "color": "#C83803", "stadium": UNIFIED_STADIUM_BG},
    "🐅 Cincinnati Bengals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png", "color": "#FB4F14", "stadium": UNIFIED_STADIUM_BG},
    "🐶 Cleveland Browns": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png", "color": "#FF3C00", "stadium": UNIFIED_STADIUM_BG},
    "⭐ Dallas Cowboys": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png", "color": "#003594", "stadium": UNIFIED_STADIUM_BG},
    "🐴 Denver Broncos": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png", "color": "#FB4F14", "stadium": UNIFIED_STADIUM_BG},
    "🦁 Detroit Lions": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png", "color": "#0076B6", "stadium": UNIFIED_STADIUM_BG},
    "🧀 Green Bay Packers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png", "color": "#203731", "stadium": UNIFIED_STADIUM_BG},
    "🐂 Houston Texans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png", "color": "#03202F", "stadium": UNIFIED_STADIUM_BG},
    "🐎 Indianapolis Colts": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png", "color": "#002C5F", "stadium": UNIFIED_STADIUM_BG},
    "🐆 Jacksonville Jaguars": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png", "color": "#006778", "stadium": UNIFIED_STADIUM_BG},
    "🏹 Kansas City Chiefs": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png", "color": "#E31837", "stadium": UNIFIED_STADIUM_BG},
    "🏴‍☠️ Las Vegas Raiders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png", "color": "#A5ACAF", "stadium": UNIFIED_STADIUM_BG},
    "⚡ Los Angeles Chargers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png", "color": "#0080C6", "stadium": UNIFIED_STADIUM_BG},
    "🐏 Los Angeles Rams": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png", "color": "#003594", "stadium": UNIFIED_STADIUM_BG},
    "🐬 Miami Dolphins": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png", "color": "#008E97", "stadium": UNIFIED_STADIUM_BG},
    "🛡️ Minnesota Vikings": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png", "color": "#4F2683", "stadium": UNIFIED_STADIUM_BG},
    "🗽 New England Patriots": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png", "color": "#002244", "stadium": UNIFIED_STADIUM_BG},
    "⚜️ New Orleans Saints": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png", "color": "#D3BC8D", "stadium": UNIFIED_STADIUM_BG},
    "🍎 New York Giants": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png", "color": "#0B2265", "stadium": UNIFIED_STADIUM_BG},
    "✈️ New York Jets": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png", "color": "#125740", "stadium": UNIFIED_STADIUM_BG},
    "🦅 Philadelphia Eagles": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png", "color": "#004C54", "stadium": UNIFIED_STADIUM_BG},
    "⛏️ Pittsburgh Steelers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png", "color": "#FFB612", "stadium": UNIFIED_STADIUM_BG},
    "⛏️ San Francisco 49ers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png", "color": "#AA0000", "stadium": UNIFIED_STADIUM_BG},
    "🌊 Seattle Seahawks": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png", "color": "#69BE28", "stadium": UNIFIED_STADIUM_BG},
    "🏴‍☠️ Tampa Bay Buccaneers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png", "color": "#D50A0A", "stadium": UNIFIED_STADIUM_BG},
    "⚔️ Tennessee Titans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png", "color": "#4B92DB", "stadium": UNIFIED_STADIUM_BG},
    "🪖 Washington Commanders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/was.png", "color": "#5A1414", "stadium": UNIFIED_STADIUM_BG},
}

NFL_TEAMS = list(NFL_TEAM_DATA.keys())

AVATAR_OPTIONS = [
    "🏈", "🐐", "⚡", "👑", "🎯", "💣", "💎", "🔥", "🛡️", "🚀", 
    "🦁", "🐯", "🐻", "🦅", "🐺", "🦈", "🐉", "💀", "👽", "🤖", 
    "⭐", "🏆", "🥇", "💪", "🎲", "🎩", "🍻", "🍕", "🍔", "💥", 
    "🔮", "🃏", "🥷", "🧙‍♂️", "🧛‍♂️", "🧟‍♂️", "🦸‍♂️", "🦹‍♂️"
]

BORDER_STYLE_OPTIONS = {
    "Classic Solid": "solid", 
    "Double Neon Pulse": "double", 
    "Dashed Gridiron": "dashed", 
    "Stealth Dotted": "dotted", 
    "Championship Ridge": "ridge", 
    "Groove Outlined": "inset"
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


# ==========================================
# HELPER & CALCULATION UTILITIES
# ==========================================

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

def send_verification_email(to_email: str, verification_link: str) -> bool:
    """Sends an account verification email via Resend."""
    try:
        html_content = f"""
        <div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" style="width: 180px; margin-bottom: 15px; filter: drop-shadow(0px 6px 15px rgba(251, 191, 36, 0.4));" />
                    <h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1>
                    <p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Weekly NFL Predictions & Wagers</p>
                </div>
                <h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3>
                <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">Thanks for registering an account with Touchdown Tokens. To lock in your weekly picks, compete on leaderboards, and claim your tokens, please authorise your email address below:</p>
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{verification_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">AUTHORISE EMAIL ADDRESS</a>
                </div>
                <p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">If you did not request this account creation or verification, you can safely ignore and delete this email.</p>
            </div>
            <div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">&copy; 2026 Touchdown Tokens. All rights reserved.</div>
        </div>
        """
        resend.Emails.send({
            "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
            "to": [to_email],
            "subject": "🏈 Authorise Your Touchdown Tokens Account",
            "html": html_content
        })
        return True
    except Exception:
        return False
