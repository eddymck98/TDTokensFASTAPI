import os
import json
import resend
import streamlit as st
from streamlit_cookies_controller import CookieController
from supabase import create_client, Client

# ==========================================
# 1. CONTROLLERS & API INITIALIZATION
# ==========================================
controller = CookieController()
resend.api_key = os.environ.get("RESEND_API_KEY") or st.secrets.get("RESEND_API_KEY", "")

# ==========================================
# 2. PROFANITY FILTER
# ==========================================
PROFANITY_FILTER = ["damn", "hell", "crap", "shit", "fuck", "bitch", "asshole", "dick", "cunt", "bastard"]

def contains_profanity(text: str) -> bool:
    """
    Checks if a given string contains any restricted profanity words.
    """
    if not text:
        return False
    text_lower = text.lower()
    words = text_lower.split()
    for p_word in PROFANITY_FILTER:
        if p_word in text_lower or any(p_word == w for w in words):
            return True
    return False

# ==========================================
# 3. EMAIL VERIFICATION & NOTIFICATIONS
# ==========================================
def send_verification_email(to_email: str, verification_link: str) -> bool:
    """
    Sends an account verification email via Resend API.
    """
    try:
        html_content = f"""<div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;"><div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);"><div style="text-align: center; margin-bottom: 30px;"><img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" style="width: 180px; margin-bottom: 15px; filter: drop-shadow(0px 6px 15px rgba(251, 191, 36, 0.4));" /><h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1><p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Weekly NFL Predictions & Wagers</p></div><h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3><p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">Thanks for registering an account with Touchdown Tokens. To lock in your weekly picks, compete on leaderboards, and claim your tokens, please authorise your email address below:</p><div style="text-align: center; margin: 35px 0;"><a href="{verification_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">AUTHORISE EMAIL ADDRESS</a></div><p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">If you did not request this account creation or verification, you can safely ignore and delete this email.</p></div><div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">&copy; 2026 Touchdown Tokens. All rights reserved.</div></div>"""
        resend.Emails.send({
            "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
            "to": [to_email],
            "subject": "🏈 Authorise Your Touchdown Tokens Account",
            "html": html_content
        })
        return True
    except Exception as e:
        st.error(f"Failed to send verification email: {e}")
        return False

# ==========================================
# 4. STATIC NFL TEAM & LEAGUE METADATA
# ==========================================
@st.cache_data
def get_static_nfl_team_data() -> dict:
    """
    Returns the comprehensive dictionary mapping NFL franchises to logos, colors, and stadium backgrounds.
    """
    return {
        "🏈 Free Agent / Neutral": {"logo": "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true", "color": "#fbbf24", "stadium": "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Arizona Cardinals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png", "color": "#97233F", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Atlanta Falcons": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png", "color": "#A71930", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟣 Baltimore Ravens": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png", "color": "#241773", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Buffalo Bills": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png", "color": "#00338D", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Carolina Panthers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png", "color": "#0085CA", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟠 Chicago Bears": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png", "color": "#C83803", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟠 Cincinnati Bengals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png", "color": "#FB4F14", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🟤 Cleveland Browns": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png", "color": "#FF3C00", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Dallas Cowboys": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png", "color": "#003594", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟠 Denver Broncos": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png", "color": "#FB4F14", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Detroit Lions": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png", "color": "#0076B6", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟢 Green Bay Packers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png", "color": "#203731", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Houston Texans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png", "color": "#03202F", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Indianapolis Colts": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png", "color": "#002C5F", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🐆 Jacksonville Jaguars": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png", "color": "#006778", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Kansas City Chiefs": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png", "color": "#E31837", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🪙 Las Vegas Raiders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png", "color": "#A5ACAF", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "⚡ Los Angeles Chargers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png", "color": "#0080C6", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟡 Los Angeles Rams": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png", "color": "#003594", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🐬 Miami Dolphins": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png", "color": "#008E97", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟣 Minnesota Vikings": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png", "color": "#4F2683", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔵 New England Patriots": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png", "color": "#002244", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "⚜️ New Orleans Saints": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png", "color": "#D3BC8D", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🔵 New York Giants": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png", "color": "#0B2265", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟢 New York Jets": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png", "color": "#125740", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🦅 Philadelphia Eagles": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png", "color": "#004C54", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟡 Pittsburgh Steelers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png", "color": "#FFB612", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 San Francisco 49ers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png", "color": "#AA0000", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🟢 Seattle Seahawks": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png", "color": "#69BE28", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Tampa Bay Buccaneers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png", "color": "#D50A0A", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Tennessee Titans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png", "color": "#4B92DB", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Washington Commanders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/was.png", "color": "#5A1414", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
    }

NFL_TEAM_DATA = get_static_nfl_team_data()
NFL_TEAMS = list(NFL_TEAM_DATA.keys())

AVATAR_OPTIONS = [
    "🏈", "🐐", "⚡", "👑", "🎯", "💣", "💎", "🔥", "🛡️", "🚀", "🦁", "🐯", "🐻", 
    "🦅", "🐺", "🦈", "🐉", "💀", "👽", "🤖", "⭐", "🏆", "🥇", "💪", "🎲", "🎩", 
    "🍻", "🍕", "🍔", "💥", "🔮", "🃏", "🥷", "🧙‍♂️", "🧛‍♂️", "🧟‍♂️", "🦸‍♂️", "🦹‍♂️"
]

BORDER_STYLE_OPTIONS = {
    "Classic Solid": "solid",
    "Double Neon Pulse": "double",
    "Dashed Gridiron": "dashed",
    "Stealth Dotted": "dotted",
    "Championship Ridge": "ridge",
    "Groove Outlined": "inset"
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
