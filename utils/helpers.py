PROFANITY_FILTER = ["damn", "hell", "crap", "shit", "fuck", "bitch", "asshole", "dick", "cunt", "bastard"]

def contains_profanity(text: str) -> bool:
    """Checks if a string contains restricted profanity words."""
    if not text:
        return False
    text_lower = text.lower()
    words = text_lower.split()
    return any(p_word in text_lower or any(p_word == w for w in words) for p_word in PROFANITY_FILTER)

def get_static_nfl_team_data():
    """Returns brand colors, logos, and stadium backgrounds for NFL teams."""
    return {
        "🏈 Free Agent / Neutral": {
            "logo": "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true",
            "color": "#fbbf24",
            "stadium": "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"
        },
        "🔴 Arizona Cardinals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png", "color": "#97233F"},
        "🔴 Atlanta Falcons": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png", "color": "#A71930"},
        "🟣 Baltimore Ravens": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png", "color": "#241773"},
        "🔴 Buffalo Bills": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png", "color": "#00338D"},
        "🔵 Carolina Panthers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png", "color": "#0085CA"},
        "🟠 Chicago Bears": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png", "color": "#C83803"},
        "🟠 Cincinnati Bengals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png", "color": "#FB4F14"},
        "🟤 Cleveland Browns": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png", "color": "#FF3C00"},
        "🔵 Dallas Cowboys": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png", "color": "#003594"},
        "🟠 Denver Broncos": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png", "color": "#FB4F14"},
        "🔵 Detroit Lions": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png", "color": "#0076B6"},
        "🟢 Green Bay Packers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png", "color": "#203731"},
        "🔴 Houston Texans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png", "color": "#03202F"},
        "🔵 Indianapolis Colts": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png", "color": "#002C5F"},
        "🐆 Jacksonville Jaguars": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png", "color": "#006778"},
        "🔴 Kansas City Chiefs": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png", "color": "#E31837"},
        "🪙 Las Vegas Raiders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png", "color": "#A5ACAF"},
        "⚡ Los Angeles Chargers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png", "color": "#0080C6"},
        "🟡 Los Angeles Rams": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png", "color": "#003594"},
        "🐬 Miami Dolphins": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png", "color": "#008E97"},
        "🟣 Minnesota Vikings": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png", "color": "#4F2683"},
        "🔵 New England Patriots": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png", "color": "#002244"},
        "⚜️ New Orleans Saints": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png", "color": "#D3BC8D"},
        "🔵 New York Giants": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png", "color": "#0B2265"},
        "🟢 New York Jets": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png", "color": "#125740"},
        "🦅 Philadelphia Eagles": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png", "color": "#004C54"},
        "🟡 Pittsburgh Steelers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png", "color": "#FFB612"},
        "🔴 San Francisco 49ers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png", "color": "#AA0000"},
        "🟢 Seattle Seahawks": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png", "color": "#69BE28"},
        "🔴 Tampa Bay Buccaneers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png", "color": "#D50A0A"},
        "🔵 Tennessee Titans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png", "color": "#4B92DB"},
        "🔴 Washington Commanders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/was.png", "color": "#5A1414"}
    }

MASTER_BADGES = {
    "token_tycoon": {"name": "Token Tycoon", "icon": "🪙", "desc": "Accumulate 50+ total tokens."},
    "gridiron_prophet": {"name": "Gridiron Prophet", "icon": "🔮", "desc": "Maintain a high prediction accuracy."},
    "down_bad": {"name": "Down Bad", "icon": "📉", "desc": "Hit 0 token balance and live to tell the tale."},
    "touchdown_machine": {"name": "Touchdown Machine", "icon": "🏈", "desc": "Successfully hit multiple TD scorer bonuses."}
}

AVAILABLE_TITLES = [
    "Rookie Predictor",
    "The Oracle",
    "Token Tycoon",
    "Gridiron Prophet",
    "Underdog Whisperer",
    "Down Bad Survivor"
]

def sync_and_get_user_badges(user_id: str):
    """Fetches or checks unlocked badges for the user from Supabase."""
    from utils.database import get_supabase_client
    supabase = get_supabase_client()
    try:
        res = supabase.table("user_badges").select("badge_key").eq("user_id", user_id).execute()
        return [r["badge_key"] for r in res.data] if res.data else []
    except Exception:
        return []
