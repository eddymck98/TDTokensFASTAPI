import os
import json
import random
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_cookies_controller import CookieController
from supabase import create_client, Client

# Import modularized components
from dependencies import (
    NFL_TEAM_DATA, NFL_TEAMS, AVATAR_OPTIONS, BORDER_STYLE_OPTIONS,
    MASTER_BADGES, AVAILABLE_TITLES, DEFAULT_QUESTION_TEMPLATES, contains_profanity
)
from database import (
    get_supabase_client, get_cached_profiles, get_cached_weekly_questions,
    get_cached_all_weekly_questions_meta, get_true_global_token_balance, recalculate_all_user_balances
)
from email_service import send_verification_email, send_password_reset_email
from helpers import get_earned_title, calculate_nemesis, calculate_streak
from badges_logic import sync_and_get_user_badges

# ==========================================
# 0. CONFIG & INITIALIZATION
# ==========================================
st.set_page_config(page_title="Touchdown Tokens", page_icon="🏈", layout="centered", initial_sidebar_state="collapsed")
controller = CookieController()
supabase = get_supabase_client()
query_params = st.query_params

# Password recovery / OAuth intercept
if "type" in query_params and query_params["type"] == "recovery":
    if "token" in query_params:
        try:
            res = supabase.auth.verify_otp({"token": query_params["token"], "type": "recovery"})
            if res and res.session:
                supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                controller.set("td_tokens_session", json.dumps({"access_token": res.session.access_token, "refresh_token": res.session.refresh_token}), max_age=2592000)
        except Exception:
            pass
    st.session_state["is_password_recovery"] = True
elif "access_token" in query_params:
    try:
        supabase.auth.set_session(query_params["access_token"], query_params.get("refresh_token", query_params["access_token"]))
        st.session_state["is_password_recovery"] = True
        st.query_params.clear()
    except Exception:
        pass

st.markdown("""<script>if (window.location.hash && window.location.hash.includes('access_token')) { const hashParams = new URLSearchParams(window.location.hash.substring(1)); const accessToken = hashParams.get('access_token'); const refreshToken = hashParams.get('refresh_token') || accessToken; const type = hashParams.get('type'); if (type === 'recovery' || accessToken) { window.location.replace(window.location.pathname + '?access_token=' + accessToken + '&refresh_token=' + refreshToken + '&type=recovery'); } }</script>""", unsafe_allow_html=True)

if "user" not in st.session_state or st.session_state.user is None:
    st.session_state.user = None
    try:
        session_cookie = controller.get("td_tokens_session")
        if session_cookie:
            acc_token, ref_token = None, None
            if isinstance(session_cookie, dict):
                acc_token, ref_token = session_cookie.get("access_token"), session_cookie.get("refresh_token")
            elif isinstance(session_cookie, str):
                if session_cookie.startswith("{"):
                    token_data = json.loads(session_cookie)
                    acc_token, ref_token = token_data.get("access_token"), token_data.get("refresh_token")
                else:
                    acc_token = ref_token = session_cookie
            if acc_token and ref_token:
                res = supabase.auth.set_session(acc_token, ref_token)
                if res and res.user:
                    st.session_state.user = res.user
                    if res.session:
                        controller.set("td_tokens_session", json.dumps({"access_token": res.session.access_token, "refresh_token": res.session.refresh_token}), max_age=2592000)
                    st.rerun()
    except Exception:
        pass

if "form_refresh" not in st.session_state:
    st.session_state.form_refresh = 0
if "signup_success_email" not in st.session_state:
    st.session_state.signup_success_email = None

# Fetch user theme info
user_team_color, user_team_logo, user_stadium_bg = "#fbbf24", "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true", "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"
if st.session_state.user:
    try:
        res = supabase.table("profiles").select("favorite_team").eq("id", st.session_state.user.id).single().execute()
        if res.data:
            t_info = NFL_TEAM_DATA.get(res.data.get("favorite_team", "🏈 Free Agent / Neutral"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
            user_team_color, user_team_logo, user_stadium_bg = t_info["color"], t_info["logo"], t_info["stadium"]
    except Exception:
        pass

# Global CSS Injector
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&family=Teko:wght@500;700&display=swap');
    .stMainBlockContainer, div[data-testid="stMainBlockContainer"] {{ padding-top: 1rem !important; }}
    header[data-testid="stHeader"] {{ background: transparent !important; }}
    .stApp, div[data-testid="stAppViewContainer"] {{ background: radial-gradient(circle at 50% 20%, rgba(15, 23, 42, 0.90), rgba(7, 13, 25, 0.99)), url('{user_team_logo}') center center / 28% no-repeat fixed, url('{user_stadium_bg}') center center / cover no-repeat fixed !important; color: #f8fafc !important; font-family: 'Inter', sans-serif !important; }}
    section[data-testid="stSidebar"] {{ display: none !important; }}
    a, a:visited, a:hover, a:active {{ color: #38bdf8 !important; text-decoration: none !important; }}
    p, span, label, div[data-testid="stMarkdownContainer"] {{ color: #f8fafc !important; }}
    .nfl-header {{ text-align: center; padding: 0px 0 4px 0; margin-top: -25px; }}
    .nfl-subtitle {{ font-family: 'Teko', sans-serif; font-size: 24px; letter-spacing: 5px; color: #93c5fd; text-transform: uppercase; margin-top: -4px; text-shadow: 0 2px 10px rgba(0,0,0,0.8); }}
    .header-logo {{ width: 240px; filter: drop-shadow(0px 10px 22px {user_team_color}cc); border-radius: 12px; }}
    @keyframes teamPulse {{ 0% {{ box-shadow: 0 0 12px {user_team_color}33; }} 50% {{ box-shadow: 0 0 32px {user_team_color}bb; }} 100% {{ box-shadow: 0 0 12px {user_team_color}33; }} }}
    .sticky-balance-bar {{ position: sticky; top: 0; z-index: 999; background: rgba(15, 23, 42, 0.94); border: 1px solid rgba(255, 255, 255, 0.12); border-bottom: 3px solid {user_team_color}; padding: 10px 22px; margin-top: 4px; margin-bottom: 20px; border-radius: 0 0 16px 16px; backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); display: flex; justify-content: space-between; align-items: center; box-shadow: 0 10px 30px rgba(0,0,0,0.7); }}
    .hero-banner {{ background: linear-gradient(135deg, rgba(30, 58, 138, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(255, 255, 255, 0.15); border-top: 4px solid {user_team_color}; border-radius: 20px; padding: 28px; margin-bottom: 25px; backdrop-filter: blur(16px); box-shadow: 0 12px 35px rgba(0,0,0,0.6); animation: teamPulse 3.5s infinite ease-in-out; display: flex; justify-content: space-between; align-items: center; }}
    .hero-tokens-val {{ font-family: 'Bebas Neue', sans-serif; font-size: 64px; color: {user_team_color} !important; letter-spacing: 2px; line-height: 1; margin: 0; text-shadow: 0 4px 15px {user_team_color}88; }}
    .champion-card {{ background: linear-gradient(135deg, rgba(120, 53, 15, 0.92) 0%, rgba(180, 83, 9, 0.92) 50%, rgba(245, 158, 11, 0.92) 100%); padding: 32px; border-radius: 18px; color: #ffffff !important; text-align: center; border: 1px solid rgba(255, 255, 255, 0.25); border-top: 4px solid #fbbf24; margin-bottom: 30px; backdrop-filter: blur(14px); box-shadow: 0 10px 35px rgba(0,0,0,0.6); animation: teamPulse 2s infinite ease-in-out; }}
    .mvp-banner {{ background: linear-gradient(135deg, rgba(147, 51, 234, 0.90) 0%, rgba(30, 58, 138, 0.94) 100%); border: 1px solid rgba(192, 132, 252, 0.4); border-top: 3px solid #c084fc; padding: 22px; border-radius: 16px; margin-bottom: 22px; text-align: center; backdrop-filter: blur(14px); box-shadow: 0 10px 30px rgba(192, 132, 252, 0.35); }}
    .trophy-card-unlocked {{ background: linear-gradient(135deg, rgba(30, 41, 59, 0.90) 0%, rgba(15, 23, 42, 0.94) 100%); border: 1px solid rgba(255, 255, 255, 0.12); border-left: 4px solid {user_team_color}; padding: 16px; border-radius: 14px; margin-bottom: 14px; backdrop-filter: blur(12px); box-shadow: 0 6px 18px rgba(0,0,0,0.4); }}
    .trophy-card-locked {{ background: rgba(15, 23, 42, 0.55); border: 1px dashed rgba(255, 255, 255, 0.18); padding: 16px; border-radius: 14px; margin-bottom: 14px; opacity: 0.55; }}
    .leaderboard-row {{ background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 6px 12px; margin-bottom: 6px; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); box-shadow: 0 2px 10px rgba(0,0,0,0.2); transition: all 0.2s ease; display: flex; align-items: center; justify-content: space-between; }}
    .leaderboard-row:hover {{ transform: translateY(-1px); border-color: rgba(255, 255, 255, 0.25); box-shadow: 0 4px 15px {user_team_color}33; }}
    .podium-rank-1 {{ border: 1px solid rgba(251, 191, 36, 0.5) !important; border-left: 4px solid #fbbf24 !important; background: linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important; }}
    .podium-rank-2 {{ border: 1px solid rgba(148, 163, 184, 0.5) !important; border-left: 4px solid #94a3b8 !important; background: linear-gradient(135deg, rgba(148, 163, 184, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important; }}
    .podium-rank-3 {{ border: 1px solid rgba(180, 83, 9, 0.5) !important; border-left: 4px solid #b45309 !important; background: linear-gradient(135deg, rgba(180, 83, 9, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important; }}
    .stat-pill-container {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }}
    .stat-pill {{ background: rgba(30, 41, 59, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 0px 6px; font-size: 9px; font-weight: 600; color: #cbd5e1; display: inline-flex; align-items: center; gap: 3px; }}
    .vs-card, .timer-card {{ background: rgba(15, 23, 42, 0.90); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 3px solid {user_team_color}; padding: 22px; border-radius: 16px; text-align: center; backdrop-filter: blur(16px); box-shadow: 0 10px 35px rgba(0,0,0,0.5); }}
    .timer-card {{ margin-bottom: 22px; padding: 18px; }}
    .chat-bubble {{ background-color: rgba(15, 23, 42, 0.88); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); padding: 14px 18px; border-radius: 12px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }}
    .summary-box {{ background-color: rgba(15, 23, 42, 0.88) !important; backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); border-left: 4px solid {user_team_color} !important; padding: 20px; border-radius: 14px; color: #f8fafc !important; margin-top: 16px; box-shadow: 0 8px 28px rgba(0,0,0,0.35); }}
    .rule-card {{ background: linear-gradient(135deg, rgba(30, 41, 59, 0.82) 0%, rgba(15, 23, 42, 0.92) 100%); border: 1px solid rgba(255, 255, 255, 0.1); border-top: 3px solid {user_team_color}; border-radius: 16px; padding: 24px; margin-bottom: 20px; backdrop-filter: blur(16px); box-shadow: 0 10px 30px rgba(0,0,0,0.4); }}
    .rule-step-num {{ font-family: 'Bebas Neue', sans-serif; font-size: 28px; color: {user_team_color}; letter-spacing: 2px; margin-bottom: 4px; }}
    div[data-testid="stHorizontalBlock"] div[data-baseweb="tab-list"], div[data-baseweb="tab-list"] {{ gap: 6px; background-color: rgba(11, 15, 25, 0.6); padding: 6px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); margin-bottom: 20px; overflow-x: auto; }}
    button[data-baseweb="tab"] {{ background: rgba(15, 23, 42, 0.75) !important; border: 1px solid rgba(255, 255, 255, 0.08) !important; border-radius: 10px !important; padding: 8px 14px !important; transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important; }}
    button[data-baseweb="tab"]:hover {{ background: rgba(30, 41, 59, 0.9) !important; border-color: rgba(255, 255, 255, 0.2) !important; transform: translateY(-1px); }}
    button[data-baseweb="tab"] * {{ font-family: 'Teko', sans-serif !important; font-size: 19px !important; letter-spacing: 1.2px !important; color: #94a3b8 !important; }}
    button[aria-selected="true"] {{ background: linear-gradient(135deg, rgba(30, 58, 138, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%) !important; border: 1px solid rgba(255, 255, 255, 0.25) !important; border-top: 3px solid {user_team_color} !important; box-shadow: 0 6px 20px {user_team_color}44 !important; }}
    button[aria-selected="true"] * {{ color: #ffffff !important; font-weight: 700 !important; }}
    .stSelectbox div[data-baseweb="select"] > div, div[data-baseweb="select"] > div, div[data-baseweb="base-input"], [data-baseweb="input"], [data-baseweb="tag"] {{ background-color: rgba(15, 23, 42, 0.90) !important; color: #ffffff !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; }}
    div[data-baseweb="select"] span, div[data-baseweb="select"] div, ul[data-baseweb="menu"], li[data-baseweb="option"], div[role="listbox"], div[role="dialog"] {{ background-color: #0f172a !important; color: #ffffff !important; }}
    div[role="option"]:hover {{ background-color: #1e3a8a !important; color: #38bdf8 !important; }}
    div.stButton > button, div.stButton > button:active, div.stButton > button:focus, button[kind="secondary"], button[kind="secondary"]:active, button[kind="secondary"]:focus {{ background-color: rgba(30, 41, 59, 0.9) !important; color: #ffffff !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 12px !important; font-family: 'Teko', sans-serif !important; font-size: 22px !important; }}
    div.stButton > button:hover {{ border-color: #38bdf8 !important; color: #38bdf8 !important; }}
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button {{ background: linear-gradient(135deg, {user_team_color} 0%, #d97706 100%) !important; color: #000000 !important; font-family: 'Teko', sans-serif !important; font-size: 25px !important; letter-spacing: 2px !important; text-transform: uppercase !important; border-radius: 12px !important; border: none !important; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important; box-shadow: 0 6px 20px rgba(0,0,0,0.5); }}
    div.stButton > button[kind="primary"]:hover, div.stFormSubmitButton > button:hover {{ transform: translateY(-2px); box-shadow: 0 10px 30px {user_team_color}99 !important; }}
    details[data-testid="stExpander"] {{ background-color: rgba(15, 23, 42, 0.85) !important; border: 1px solid rgba(255, 255, 255, 0.12) !important; border-radius: 12px !important; }}
    details[data-testid="stExpander"] summary {{ color: #f8fafc !important; }}
    details[data-testid="stExpander"] summary:hover {{ color: #38bdf8 !important; }}
    .stTextInput > label, .stNumberInput > label, .stRadio > label, .stSelectbox > label {{ color: #f8fafc !important; font-weight: 600 !important; font-size: 16px !important; letter-spacing: 0.5px; }}
    .stTextInput input, .stNumberInput input {{ background-color: rgba(15, 23, 42, 0.92) !important; color: #ffffff !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 12px !important; }}
    </style>
    """, unsafe_allow_html=True)

st.markdown("""<div class="nfl-header"><img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" class="header-logo" alt="Touchdown Tokens Logo" /><div class="nfl-subtitle">Weekly NFL Predictions & Wagers</div></div>""", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def get_cached_leaderboard_stats(allowed_peer_ids=None, selected_league_id=None):
    leader_res = get_cached_profiles(); stats = []
    if not leader_res:
        return stats
    for p in leader_res:
        if allowed_peer_ids is not None and p["id"] not in allowed_peer_ids:
            continue
        true_global_tokens = get_true_global_token_balance(p["id"])
        correct_tds = supabase.table("touchdown_picks").select("*").eq("user_id", p["id"]).eq("is_correct", True).execute().data
        u_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", p["id"]).execute().data
        wins, total_graded = 0, 0
        for b in u_bets:
            w_ans = b.get("weekly_questions", {}).get("winning_answer")
            if w_ans in ["Yes", "No"]:
                total_graded += 1
                if b["pick"] == w_ans:
                    wins += 1
        nem_name, nem_score = calculate_nemesis(supabase, p["id"], allowed_peer_ids=allowed_peer_ids)
        stats.append({**p, "tokens": true_global_tokens, "correct_tds": len(correct_tds) if correct_tds else 0, "win_rate": int((wins / total_graded) * 100) if total_graded > 0 else 0, "total_bets": total_graded, "nemesis_name": nem_name, "nemesis_score": nem_score, "streak": calculate_streak(supabase, p["id"])})
    return sorted(stats, key=lambda x: (-x["tokens"], -x["correct_tds"], x["full_name"]))

is_signin_locked, is_signup_locked = False, False
try:
    is_signin_locked = (supabase.table("weekly_questions").select("winning_answer").eq("week_number", 998).execute().data or [{"winning_answer": ""}])[0]["winning_answer"] == "LOCKED"
except Exception:
    pass
try:
    is_signup_locked = (supabase.table("weekly_questions").select("winning_answer").eq("week_number", 997).execute().data or [{"winning_answer": ""}])[0]["winning_answer"] == "LOCKED"
except Exception:
    pass

# ==========================================
# 0. PASSWORD RECOVERY SCREEN INTERCEPT
# ==========================================
if st.session_state.get("is_password_recovery", False):
    st.title("Touchdown Tokens")
    st.subheader("🔑 Set a New Password")
    st.caption("Please choose a secure new password for your account.")

    with st.form("password_recovery_screen_form"):
        recovery_email = st.text_input("Confirm Your Account Email")
        new_p1 = st.text_input("New Password (min 6 chars)", type="password")
        new_p2 = st.text_input("Confirm New Password", type="password")
        submit_new_pass = st.form_submit_button("Update Password & Log In 🚀", type="primary")

        if submit_new_pass:
            if len(new_p1) < 6:
                st.warning("Password must be at least 6 characters long.")
            elif new_p1 != new_p2:
                st.error("Passwords do not match.")
            elif not recovery_email.strip():
                st.warning("Please enter your email address.")
            else:
                try:
                    token_val = st.query_params.get("token", "")
                    if token_val:
                        res = supabase.auth.verify_otp({"email": recovery_email.strip(), "token": token_val, "type": "recovery"})
                        if res and res.session:
                            supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                    supabase.auth.update_user({"password": new_p1})
                    st.session_state["is_password_recovery"] = False
                    st.query_params.clear()
                    st.success("Password updated successfully! You can now log in.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update password: {e}")

    if st.button("Cancel & Return to Login"):
        st.session_state["is_password_recovery"] = False
        st.query_params.clear()
        st.rerun()

# ==========================================
# 1. LOGIN & SIGNUP SCREEN
# ==========================================
elif st.session_state.user is None:
    st.title("Touchdown Tokens")

    if st.session_state.get("signup_success_email"):
        success_email_val = st.session_state["signup_success_email"]
        st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 35px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-top: 20px;"><h2 style="color: #fbbf24; font-family: 'Bebas Neue', Arial, sans-serif; font-size: 36px; letter-spacing: 2px; margin-bottom: 10px;">WELCOME TO THE LEAGUE! 🏈</h2><p style="color: #cbd5e1; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">We have successfully created your account and sent a verification email to <b style="color: #38bdf8;">{success_email_val}</b>.</p><div style="background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); padding: 18px; border-radius: 12px; margin-bottom: 25px; text-align: left;"><b style="color: #ffffff; font-size: 15px;">Next Steps & Useful Links:</b><ul style="color: #cbd5e1; font-size: 14px; margin-top: 8px; margin-bottom: 0; padding-left: 20px; line-height: 1.6;"><li>Check your email inbox (and spam folder) for the verification message.</li><li>Click the <b>Authorise Email Address</b> verification button inside the email.</li></ul></div></div>""", unsafe_allow_html=True)
        col_btn_back1, col_btn_back2 = st.columns(2)
        with col_btn_back1:
            if st.button("Proceed to Log In 🔒", type="primary"):
                st.session_state.signup_success_email = None
                st.rerun()
        with col_btn_back2:
            if st.button("Sign Up Another Account 📝"):
                st.session_state.signup_success_email = None
                st.rerun()
    else:
        tab_login, tab_signup = st.tabs(["🔒 Log In", "📝 Sign Up"])
        with tab_login:
            st.subheader("Login to Your Account")
            if is_signin_locked:
                st.error("🔒 **SIGN-IN LOCKED:** The Admin has temporarily disabled log-ins. Please check back soon!")
            else:
                login_email = st.text_input("Email", key="login_email")
                login_password = st.text_input("Password", type="password", key="login_password")
                if st.button("Login"):
                    if login_email and login_password:
                        try:
                            auth_response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                            user = auth_response.user
                            if user and user.email_confirmed_at:
                                st.session_state["user"] = user
                                if auth_response.session:
                                    controller.set("td_tokens_session", json.dumps({"access_token": auth_response.session.access_token, "refresh_token": auth_response.session.refresh_token}), max_age=2592000)
                                st.success("Successfully logged in!")
                                st.rerun()
                            else:
                                supabase.auth.sign_out()
                                st.error("Please authorise your email first before logging in. Check your inbox for the verification link.")
                        except Exception:
                            st.error("Invalid login credentials or unverified account. Please authorise first.")
                    else:
                        st.warning("Please enter both email and password.")

                st.write("")
                with st.expander("🔑 Forgot Password?"):
                    st.caption("Enter your email address to receive a password reset link.")
                    reset_email = st.text_input("Your Account Email", key="reset_email_input")
                    if st.button("Send Reset Link"):
                        if reset_email:
                            try:
                                service_key = os.environ.get("SUPABASE_SERVICE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
                                url = os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
                                admin_supabase = create_client(url, service_key) if service_key and url else supabase
                                response = admin_supabase.auth.admin.generate_link({"type": "recovery", "email": reset_email.strip()})
                                if response and hasattr(response, "properties") and response.properties:
                                    props = response.properties
                                    action_link = props.get("action_link") if isinstance(props, dict) else getattr(props, "action_link", None)
                                    email_otp = props.get("email_otp") if isinstance(props, dict) else getattr(props, "email_otp", None)
                                    recovery_link = f"https://tdtokens.co.uk/?token={email_otp}&type=recovery" if email_otp else (f"https://tdtokens.co.uk/?token={action_link.split('token=')[1].split('&')[0]}&type=recovery" if action_link and "token=" in action_link else action_link)
                                    if recovery_link:
                                        send_password_reset_email(reset_email.strip(), recovery_link)
                                        st.success("Password reset email sent via Resend! Check your inbox.")
                                    else:
                                        st.error("Could not retrieve recovery link properties from the response.")
                                else:
                                    st.error("Could not generate recovery link for this email.")
                            except Exception as e:
                                st.error(f"Error sending password reset email: {e}")
                        else:
                            st.warning("Please enter your email address.")

        with tab_signup:
            st.subheader("Create an Account")
            if is_signup_locked:
                st.error("🔒 **SIGN-UP LOCKED:** The Admin has temporarily disabled new account registrations. Please check back soon!")
            else:
                st.caption("New players start with 10 free tokens!")
                col_fn, col_sn = st.columns(2)
                with col_fn:
                    reg_first_name = st.text_input("First Name", key="reg_first_name")
                with col_sn:
                    reg_surname = st.text_input("Surname", key="reg_surname")
                signup_email = st.text_input("Email Address", key="signup_email")
                signup_password = st.text_input("Password (min 6 chars)", type="password", key="signup_password")

                with st.expander("📖 View Touchdown Tokens Terms of Service & User Agreement"):
                    st.markdown("""**TOUCHDOWN TOKENS — TERMS OF SERVICE & USER AGREEMENT**\n\n**1. Nature of the Platform & Virtual Currency**\n• *Recreational & Entertainment Purpose:* Touchdown Tokens is strictly an independent, recreational, free-to-play sports prediction and entertainment platform designed solely for amusement and community engagement among sports fans.\n• *Zero Cash Value:* All points, scores, standings, and virtual tokens ("Tokens") maintain zero real-world cash or monetary value and cannot be purchased, sold, bartered, or redeemed for currency, goods, or services.\n• *Not Gambling:* Because Tokens cannot be purchased or cashed out, the Platform does not constitute gambling, sports betting, or a lottery.\n\n**2. Eligibility & Account Registration**\n• *Eligibility:* You represent and warrant that you are of legal age in your jurisdiction to enter into a binding contract.\n• *Single Account Policy:* Each user is strictly permitted to maintain one (1) active account. Multi-accounting, automated scripts, or proxy use to manipulate rankings is prohibited.\n• *Account Security:* You are solely responsible for maintaining the confidentiality of your credentials and all activity under your account.\n\n**3. Gameplay, Submissions & Deadlines**\n• *Lockout Deadlines:* Weekly picks and touchdown scorer bonus selections lock strictly 15 minutes prior to the first scheduled Sunday NFL kickoff. Late submissions are not accepted.\n• *Final Overrides:* You may update picks freely before lockout. Your final submitted state at the moment of lockout constitutes your official, binding entry. Previous iterations are overwritten.\n• *Grading:* All scenario outcomes and standings are graded and finalized by the system administrator using official NFL statistics (powered by ESPN feeds). Administrative rulings are final.\n\n**4. Code of Conduct & Community Standards**\n• *Acceptable Use:* Users must utilize the Platform in a respectful, lawful, and sportsmanlike manner.\n• *Prohibited Conduct:* Harassment, hate speech, threats, collusion, cheating, match-fixing, or attempting to compromise database security is strictly prohibited.\n• *Enforcement:* Administrators reserve the right to moderate content, deduct tokens, suspend accounts, or permanently terminate access for violations without prior notice.\n\n**5. Intellectual Property Rights**\n• *Ownership:* All source code, design layouts, custom branding, and logos associated with Touchdown Tokens are the exclusive intellectual property of the Platform creators. Third-party team logos and sports data remain property of their respective holders.\n\n**6. Disclaimers & Limitation of Liability**\n• *As Is Basis:* The Platform is provided on an "as is" and "as available" basis without warranties of any kind.\n• *Third-Party APIs:* We rely on third-party data providers (e.g., ESPN API) and assume no liability for temporary data outages, delayed stats, or initial erroneous scoring.\n• *Postponed/Canceled Games:* In the event an NFL game is officially postponed or canceled, connected questions are voided and token wagers are fully refunded.\n• *Limitation of Liability:* Administrators and hosts shall not be held liable for any direct, indirect, or consequential damages arising out of your use of the Platform.\n\n**7. Modifications & Governing Law**\n• *Amendments:* Administrators reserve the right to modify these Terms at any time. Continued use of the Platform constitutes binding acceptance of revised terms.\n• *Governing Law:* These Terms are governed by and construed in accordance with the laws of the jurisdiction in which the Platform is primarily administered.""")

                tc_accepted = st.checkbox("I agree to the Touchdown Tokens Terms of Service & User Agreement", key="reg_tc_checkbox")
                if st.button("Sign Up"):
                    if not reg_first_name.strip():
                        st.warning("Please enter your first name.")
                    elif not reg_surname.strip():
                        st.warning("Please enter your surname.")
                    elif not signup_email.strip():
                        st.warning("Please enter your email address.")
                    elif not tc_accepted:
                        st.warning("You must accept the Terms of Service & User Agreement to create an account.")
                    else:
                        combined_full_name = f"{reg_first_name.strip()} {reg_surname.strip()}"
                        if contains_profanity(combined_full_name):
                            st.error("⚠️ Your name contains restricted language. Please choose appropriate wording.")
                        else:
                            try:
                                response = supabase.auth.sign_up({"email": signup_email.strip(), "password": signup_password})
                                if response.user:
                                    new_uid = response.user.id
                                    supabase.table("profiles").insert({"id": new_uid, "email": signup_email.strip(), "full_name": combined_full_name, "tokens": 10, "is_admin": False, "favorite_team": "🏈 Free Agent / Neutral", "bio": "Ready for Kickoff!", "avatar_emoji": "🏈", "featured_badges": [], "unlocked_badges": [], "avatar_border": "solid", "favorite_player": "", "avatar_color": "#1e3a8a", "selected_title": "🏈 Gridiron Contender", "default_league_view": "00000000-0000-0000-0000-000000000001", "email_notifications": True, "high_contrast_mode": False, "reduced_motion": False}).execute()
                                    try:
                                        supabase.table("league_members").insert({"league_id": "00000000-0000-0000-0000-000000000001", "user_id": new_uid}).execute()
                                    except Exception:
                                        pass
                                    send_verification_email(signup_email.strip(), "https://tdtokens.co.uk")
                                    try:
                                        supabase.auth.sign_out()
                                    except Exception:
                                        pass
                                    st.session_state.signup_success_email = signup_email.strip()
                                    st.rerun()
                                else:
                                    st.error("Sign up failed. Please try again.")
                            except Exception as e:
                                st.error(f"Error: {e}")

# ==========================================
# 2. MAIN LOGGED-IN GAME PORTAL
# ==========================================
else:
    user_id = st.session_state.user.id
    try:
        profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute().data
    except Exception:
        profile = None

    if not profile:
        try:
            fallback_name = st.session_state.user.email.split("@")[0].capitalize()
            supabase.table("profiles").insert({"id": user_id, "email": st.session_state.user.email, "full_name": fallback_name, "tokens": 10, "is_admin": False, "favorite_team": "🏈 Free Agent / Neutral", "bio": "Ready for Kickoff!", "avatar_emoji": "🏈", "featured_badges": [], "unlocked_badges": [], "avatar_border": "solid", "favorite_player": "", "avatar_color": "#1e3a8a", "selected_title": "🏈 Gridiron Contender", "default_league_view": "00000000-0000-0000-0000-000000000001", "email_notifications": True, "high_contrast_mode": False, "reduced_motion": False}).execute()
            try:
                supabase.table("league_members").insert({"league_id": "00000000-0000-0000-0000-000000000001", "user_id": user_id}).execute()
            except Exception:
                pass
            profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute().data
        except Exception:
            profile = {"id": user_id, "full_name": "Player", "tokens": 10, "is_admin": False, "favorite_team": "🏈 Free Agent / Neutral", "bio": "Ready for Kickoff!", "avatar_emoji": "🏈", "featured_badges": [], "unlocked_badges": [], "avatar_border": "solid", "favorite_player": "", "avatar_color": "#1e3a8a", "selected_title": "🏈 Gridiron Contender", "default_league_view": "00000000-0000-0000-0000-000000000001", "email_notifications": True, "high_contrast_mode": False, "reduced_motion": False}

    user_avatar, user_team, user_border_style, user_avatar_color = profile.get("avatar_emoji", "🏈"), profile.get("favorite_team", "🏈 Free Agent / Neutral"), profile.get("avatar_border", "solid"), profile.get("avatar_color", "#1e3a8a")
    team_data = NFL_TEAM_DATA.get(user_team, NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
    sync_and_get_user_badges(supabase, user_id, check_celebration=True, st_session_state=st.session_state)

    my_administered_leagues = supabase.table("leagues").select("id, league_name, invite_code, league_password").eq("created_by", user_id).execute().data
    is_any_league_admin = bool(my_administered_leagues) or profile.get("is_admin", False)

    weeks_res = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
    available_weeks = sorted(list(set([r["week_number"] for r in weeks_res.data]))) if weeks_res.data else []

    true_global_tokens_sidebar = get_true_global_token_balance(user_id)
    active_tokens_display = true_global_tokens_sidebar
    
    if available_weeks:
        latest_w_active, is_latest_graded = available_weeks[-1], False
        latest_week_status = supabase.table("weekly_questions").select("winning_answer").eq("week_number", latest_w_active).eq("question_number", 96).execute().data
        if latest_week_status and latest_week_status[0]["winning_answer"] == "CLOSED":
            is_latest_graded = True
        else:
            w_qs_check = supabase.table("weekly_questions").select("winning_answer").eq("week_number", latest_w_active).neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
            if w_qs_check and all(q["winning_answer"] in ["Yes", "No"] for q in w_qs_check):
                is_latest_graded = True
        if not is_latest_graded:
            user_active_bets = supabase.table("user_bets").select("wager_amount, weekly_questions(winning_answer)").eq("user_id", user_id).eq("week_number", latest_w_active).execute().data
            total_wagered_active = sum(b["wager_amount"] for b in user_active_bets if b.get("weekly_questions", {}).get("winning_answer", "Pending") not in ["Yes", "No"]) if user_active_bets else 0
            active_tokens_display = max(0, true_global_tokens_sidebar - total_wagered_active)

    st.markdown(f"""<div class="sticky-balance-bar"><div style="display: flex; align-items: center; gap: 14px;"><div style="border: 3px {user_border_style} {user_team_color}; border-radius: 10px; padding: 3px 8px; background: {user_avatar_color}; box-shadow: 0 4px 12px {user_team_color}33;"><span style="font-size: 26px;">{user_avatar}</span></div><div><b style="font-size: 16px; color: #ffffff;">{profile['full_name']}</b> <span style="font-size:11px; color:#38bdf8; margin-left:6px;">({get_earned_title(supabase, user_id)})</span><div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">{user_team}</div></div></div><div style="display: flex; align-items: center; gap: 15px;"><div style="text-align: right;"><span style="font-family: 'Bebas Neue'; font-size: 26px; color: {user_team_color};">{active_tokens_display} 🪙</span><div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Available Tokens</div></div></div></div>""", unsafe_allow_html=True)

    tabs_options = ["🏠 Home", "👤 Profile", "📖 Rules", "🎯 Bets", "📜 History", "🛡️ Leagues", "⭐ Commish", "⚙️ Settings", "🛠️ Admin"]
    if profile.get("is_admin") and is_any_league_admin:
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_league_admin, tab_settings, tab_admin = st.tabs(tabs_options)
    elif profile.get("is_admin"):
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_settings, tab_admin = st.tabs([t for t in tabs_options if t != "⭐ Commish"])
    elif is_any_league_admin:
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_league_admin, tab_settings = st.tabs([t for t in tabs_options if t != "🛠️ Admin"])
    else:
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_settings = st.tabs([t for t in tabs_options if t not in ["⭐ Commish", "🛠️ Admin"]])

    with tab_home:
        st.markdown(f"""<div class="hero-banner"><div><div style="font-size: 14px; letter-spacing: 2px; text-transform: uppercase; color: #93c5fd; font-weight: 600;">Available Balance</div><div class="hero-tokens-val">{active_tokens_display} 🪙</div><div style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">True Global Bank: <b>{true_global_tokens_sidebar} 🪙</b> (Active Wagers Deducted)</div></div><div style="text-align: right; border-left: 1px solid rgba(255,255,255,0.15); padding-left: 20px;"><div style="font-size: 12px; color: #94a3b8; text-transform: uppercase; font-weight: 700;">Welcome Back</div><div style="font-size: 18px; font-weight: bold; color: #ffffff;">{profile['full_name']}</div><div style="font-size: 11px; color: #38bdf8;">{get_earned_title(supabase, user_id)}</div></div></div>""", unsafe_allow_html=True)
        st.subheader("👁️ Your Current Weekly Picks & Share Hub")
        st.caption("Review your active entries for the upcoming week and grab a quick share text for your group chat.")

        if not available_weeks:
            st.info("No active weeks available.")
        else:
            view_week = st.selectbox("Select Week to View", available_weeks, index=len(available_weeks) - 1, key="home_view_current_week_sel")
            curr_user_bets = supabase.table("user_bets").select("*, weekly_questions(question_number, question_text, winning_answer)").eq("user_id", user_id).eq("week_number", view_week).order("question_id").execute().data
            curr_user_td = supabase.table("touchdown_picks").select("player_name, is_correct").eq("user_id", user_id).eq("week_number", view_week).execute().data
            
            if not curr_user_bets and not curr_user_td:
                st.warning(f"You haven't submitted any picks for Week {view_week} yet! Head over to the 'Place Bets' tab.")
            else:
                share_lines = [f"🏈 *{profile['full_name']} - Week {view_week} Lock-Ins* 🏈"]
                for b in curr_user_bets:
                    q_num, raw_q_text_home, pick_val, wager_amt, w_ans = b.get("weekly_questions", {}).get("question_number", "?"), b.get("weekly_questions", {}).get("question_text", ""), b["pick"], b["wager_amount"], b.get("weekly_questions", {}).get("winning_answer", "Pending")
                    q_txt = raw_q_text_home.split(" | MATCHUP: ")[0] if " | MATCHUP: " in raw_q_text_home else raw_q_text_home
                    if w_ans in ["Yes", "No"]:
                        card_border_glow, card_shadow_glow, status_label = ("#10b981", "rgba(16, 185, 129, 0.3)", "Won ✅") if pick_val == w_ans else ("#ef4444", "rgba(239, 68, 68, 0.3)", "Lost ❌")
                    else:
                        card_border_glow, card_shadow_glow, status_label = "#38bdf8", "rgba(56, 189, 248, 0.2)", "Pending ⏳"
                    st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255, 255, 255, 0.1); border-left: 3px solid {card_border_glow}; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; box-shadow: 0 2px 10px {card_shadow_glow};"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;"><span style="font-family: 'Bebas Neue'; font-size: 13px; color: #38bdf8; letter-spacing: 1px;">Q{q_num}</span><span style="font-size: 11px; font-weight: 600; color: {card_border_glow}; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">{status_label}</span></div><div style="font-size: 13px; font-weight: 600; color: #ffffff; margin-bottom: 6px; line-height: 1.3;">{q_txt}</div><div style="display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px; color: #cbd5e1;"><span style="background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">Pick: <b style="color: {user_team_color};">{pick_val}</b></span><span style="background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">Wager: <b>{wager_amt} 🪙</b></span></div></div>""", unsafe_allow_html=True)
                    share_lines.append(f"Q{q_num}: {pick_val} ({wager_amt} tokens)")
                
                td_name, td_status = (curr_user_td[0]["player_name"], curr_user_td[0].get("is_correct")) if curr_user_td else ("None", None)
                td_glow, td_shadow, td_status_label = ("#10b981", "rgba(16, 185, 129, 0.3)", "Won (+5 🪙)") if td_status is True else ("#ef4444", "rgba(239, 68, 68, 0.3)", "Missed ❌") if td_status is False else ("#38bdf8", "rgba(56, 189, 248, 0.2)", "Pending ⏳")
                st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255, 255, 255, 0.1); border-left: 3px solid {td_glow}; border-radius: 8px; padding: 8px 12px; margin-top: 8px; margin-bottom: 12px; box-shadow: 0 2px 10px {td_shadow}; display: flex; align-items: center; justify-content: space-between;"><div style="display: flex; align-items: center; gap: 8px;"><span style="font-family: 'Bebas Neue'; font-size: 14px; color: {td_glow};">TD BONUS</span><span style="font-size: 12px; color: #ffffff;">{td_name}</span></div><span style="font-size: 11px; font-weight: 600; color: {td_glow}; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">{td_status_label}</span></div>""", unsafe_allow_html=True)
                share_lines.append(f"TD Scorer Pick: {td_name}")
                st.write("")
                st.subheader("📋 Group Chat Share Text")
                st.code("\n".join(share_lines), language="markdown")
                st.success("Copy the text box above to share your picks directly into WhatsApp or group chat!")

        graded_q_badge = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).neq("winning_answer", "Pending").neq("winning_answer", "LOCKED").order("week_number", desc=True).execute().data
        if graded_q_badge:
            latest_mvp_week = graded_q_badge[0]["week_number"]
            mvp_bets, mvp_tds = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("week_number", latest_mvp_week).execute().data, supabase.table("touchdown_picks").select("*").eq("week_number", latest_mvp_week).eq("is_correct", True).execute().data
            user_weekly_net = {}
            for b in mvp_bets:
                u, w_ans = b["user_id"], b.get("weekly_questions", {}).get("winning_answer")
                if u not in user_weekly_net:
                    user_weekly_net[u] = 0
                if w_ans in ["Yes", "No"]:
                    user_weekly_net[u] += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
            for td in mvp_tds:
                user_weekly_net[td["user_id"]] = user_weekly_net.get(td["user_id"], 0) + 5
            if user_weekly_net and max(user_weekly_net.values(), default=-1) > 0:
                top_mvp_id, top_mvp_tokens = max(user_weekly_net, key=user_weekly_net.get), user_weekly_net[max(user_weekly_net, key=user_weekly_net.get)]
                mvp_profile = supabase.table("profiles").select("full_name, avatar_emoji, favorite_team").eq("id", top_mvp_id).single().execute().data
                if mvp_profile:
                    st.markdown(f"""<div class="mvp-banner"><div style="font-size: 16px; letter-spacing: 2px; text-transform: uppercase; color: #f3e8ff;">🔥 Week {latest_mvp_week} League MVP 🔥</div><div style="font-size: 36px; font-weight: 900; margin: 5px 0; color: #ffffff;">{mvp_profile.get('avatar_emoji', '🏈')} {mvp_profile['full_name']}</div><div style="font-size: 16px; color: #d8b4fe;">Dominated the slate with <b>+{top_mvp_tokens} Net Tokens</b>! 🚀</div></div>""", unsafe_allow_html=True)

        if available_weeks:
            current_active_week = available_weeks[-1]
            st.divider()
            st.subheader(f"📊 Week {current_active_week} Community Trends & Action")
            st.caption("A snapshot of how the league is leaning on this week's active matchups.")
            live_all_bets = supabase.table("user_bets").select("question_id, pick, wager_amount, weekly_questions(question_text)").eq("week_number", current_active_week).execute().data
            if live_all_bets:
                q_stats = {}
                for b in live_all_bets:
                    q_text = b.get("weekly_questions", {}).get("question_text", "Question")
                    clean_q = q_text.split(" | MATCHUP: ")[0] if " | MATCHUP: " in q_text else q_text
                    if clean_q not in q_stats:
                        q_stats[clean_q] = {"Yes": 0, "No": 0, "TotalWager": 0, "Votes": 0}
                    q_stats[clean_q][b["pick"]] += 1
                    q_stats[clean_q]["TotalWager"] += b["wager_amount"]
                    q_stats[clean_q]["Votes"] += 1
                trend_list = [{"question": q, "consensus": f"{max(int((d['Yes']/d['Votes'])*100), 100-int((d['Yes']/d['Votes'])*100))}% {'YES' if int((d['Yes']/d['Votes'])*100) >= 50 else 'NO'}", "total_wagered": d["TotalWager"], "votes": d["Votes"]} for q, d in q_stats.items() if d["Votes"] > 0]
                if trend_list:
                    for _, row in pd.DataFrame(trend_list).sort_values(by="total_wagered", ascending=False).head(3).iterrows():
                        st.markdown(f"""<div class="summary-box"><b>🔥 Heaviest Action: {row['question']}</b><br>• <b>League Consensus:</b> {row['consensus']} ({row['votes']} total player bets)<br>• <b>Total Tokens Wagered on Matchup:</b> {row['total_wagered']} 🪙</div>""", unsafe_allow_html=True)
                else:
                    st.info("No bets placed for the current week yet. Be the first to lock in your picks!")
            else:
                st.info("No bets placed for the current week yet. Be the first to lock in your picks!")

        st.divider()
        st.subheader("📊 Last Week's Performance Summary")
        all_graded_weeks_meta, graded_weeks_set = get_cached_all_weekly_questions_meta(), set()
        closed_markers = supabase.table("weekly_questions").select("week_number").eq("question_number", 96).eq("winning_answer", "CLOSED").execute().data
        if closed_markers:
            [graded_weeks_set.add(cm["week_number"]) for cm in closed_markers]
        if all_graded_weeks_meta:
            w_map = {}
            for q in all_graded_weeks_meta:
                if q["week_number"] not in w_map:
                    w_map[q["week_number"]] = []
                if q.get("question_number", 0) <= 10:
                    w_map[q["week_number"]].append(q["winning_answer"])
            [graded_weeks_set.add(w) for w, ans_list in w_map.items() if ans_list and all(a in ["Yes", "No"] for a in ans_list)]
        
        graded_weeks_list = sorted(list(graded_weeks_set))
        if not graded_weeks_list:
            st.info("No weeks have been graded yet. Place your bets for Week 1 to get started!")
        else:
            latest_graded_week = graded_weeks_list[-1]
            lw_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", user_id).eq("week_number", latest_graded_week).execute().data
            lw_td = supabase.table("touchdown_picks").select("*").eq("user_id", user_id).eq("week_number", latest_graded_week).execute().data
            if not lw_bets and not lw_td:
                st.warning(f"You did not submit any bets or touchdown picks for Week {latest_graded_week}.")
            else:
                bet_gains, bet_losses, correct_count, total_bets_placed = 0, 0, 0, len(lw_bets)
                for b in lw_bets:
                    w_ans = b.get("weekly_questions", {}).get("winning_answer")
                    if w_ans in ["Yes", "No"]:
                        if b["pick"] == w_ans:
                            bet_gains += b["wager_amount"]
                            correct_count += 1
                        else:
                            bet_losses += b["wager_amount"]
                td_record = lw_td[0] if lw_td else None
                if td_record is None or td_record.get("is_correct") is None:
                    td_is_graded, td_bonus, td_display_status = False, 0, "⏳ Pending (Awaiting Admin Grading)"
                else:
                    td_is_graded, td_bonus, td_display_status = True, 5 if str(td_record.get("is_correct")).lower() == "true" else 0, "✅ Correct (+5 Tokens)" if str(td_record.get("is_correct")).lower() == "true" else "❌ Incorrect (Missed)"
                td_player, net_total = td_record["player_name"] if td_record else "None", bet_gains - bet_losses + td_bonus
                celeb_key = f"celebrated_week_{latest_graded_week}_{user_id}"
                if net_total > 0 and not st.session_state.get(celeb_key, False):
                    st.balloons()
                    st.session_state[celeb_key] = True
                st.markdown(f"### Week {latest_graded_week} Results")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Net Tokens Earned", f"{'+' if net_total >= 0 else ''}{net_total} 🪙")
                with col2:
                    st.metric("Questions Correct", f"{correct_count} / {total_bets_placed}")
                with col3:
                    if td_is_graded:
                        st.metric("TD Scorer Bonus", f"+{td_bonus} 🪙" if td_bonus > 0 else "0 🪙")
                    else:
                        st.metric("TD Scorer Bonus", "Pending ⏳")
                st.markdown(f"""<div class="summary-box"><b>Week {latest_graded_week} Breakdown:</b><br>• <b>Question Wins:</b> +{bet_gains} Tokens (Net Profit)<br>• <b>Question Losses:</b> -{bet_losses} Tokens<br>• <b>Touchdown Scorer Pick:</b> '{td_player}' ({td_display_status})</div>""", unsafe_allow_html=True)

        st.divider()
        st.subheader("📊 Token History Graph")
        history_bets_all = supabase.table("user_bets").select("week_number, wager_amount, pick, weekly_questions(winning_answer)").eq("user_id", user_id).execute().data
        all_td_history = supabase.table("touchdown_picks").select("week_number, is_correct").eq("user_id", user_id).eq("is_correct", True).execute().data
        td_wins_map = {td["week_number"]: 5 for td in all_td_history}
        
        if history_bets_all or td_wins_map:
            week_tokens, curr_tokens = {0: 10}, 10
            for w in sorted(list(set([b["week_number"] for b in history_bets_all] + list(td_wins_map.keys())))):
                for b in [b for b in history_bets_all if b["week_number"] == w]:
                    w_ans = b.get("weekly_questions", {}).get("winning_answer")
                    if w_ans in ["Yes", "No"]:
                        curr_tokens += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
                if w in td_wins_map:
                    curr_tokens += 5
                week_tokens[w] = max(0, curr_tokens)
            
            chart_weeks, chart_vals = list(week_tokens.keys()), list(week_tokens.values())
            def hex_to_rgba(h, alpha=0.25):
                h = h.lstrip("#")
                return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alpha})" if len(h) == 6 else f"rgba(251, 191, 36, {alpha})"
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[f"Week {w}" if w > 0 else "Start" for w in chart_weeks], y=chart_vals, mode="lines+markers", name="Token Bank", line=dict(color=user_team_color, width=4, shape="spline"), marker=dict(size=10, color=user_team_color, line=dict(color="#ffffff", width=2)), fill="tozeroy", fillcolor=hex_to_rgba(user_team_color, 0.25), hovertemplate="<b>%{x}</b><br>Token Balance: %{y} 🪙<extra></extra>"))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15, 23, 42, 0.75)", margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", tickfont=dict(color="#cbd5e1", family="Inter", size=12), zeroline=False), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", tickfont=dict(color="#cbd5e1", family="Inter", size=12), zeroline=False), hoverlabel=dict(bgcolor="#0f172a", font_color="#ffffff", font_family="Inter"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No token history data available yet.")

    with tab_profile:
        st.header("👤 Profile & Customization Hub")
        st.caption("Personalize your display avatar, title nametag, border style, avatar color, favorite player, favorite team, and featured badges!")
        curr_team = profile.get("favorite_team", "🏈 Free Agent / Neutral")
        new_team = st.selectbox("Favorite NFL Team", NFL_TEAMS, index=NFL_TEAMS.index(curr_team) if curr_team in NFL_TEAMS else 0)
        selected_team_data = NFL_TEAM_DATA.get(new_team, NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
        col_logo, col_info = st.columns([1, 4])
        with col_logo:
            st.image(selected_team_data["logo"], width=75)
        with col_info:
            st.markdown(f"### {new_team}")

        user_badges_for_titles = sync_and_get_user_badges(supabase, user_id)
        unlocked_title_options, locked_title_info = [], []
        for title_name, info in AVAILABLE_TITLES.items():
            if info["badge"] is None or info["badge"] in user_badges_for_titles:
                unlocked_title_options.append(title_name)
            else:
                locked_title_info.append((title_name, info["req"]))
        
        curr_selected_title = profile.get("selected_title", "🏈 Gridiron Contender")
        if curr_selected_title not in unlocked_title_options:
            curr_selected_title = unlocked_title_options[0] if unlocked_title_options else "🏈 Gridiron Contender"
        
        with st.form("profile_customization_form"):
            new_display_name = st.text_input("Display Name", value=profile.get("full_name", ""))
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                new_title = st.selectbox("Active Nametag Title", unlocked_title_options, index=unlocked_title_options.index(curr_selected_title) if curr_selected_title in unlocked_title_options else 0, help="Select from your unlocked prestigious titles!")
            with col_t2:
                curr_avatar = profile.get("avatar_emoji", "🏈")
                new_avatar = st.selectbox("Avatar Emoji", AVATAR_OPTIONS, index=AVATAR_OPTIONS.index(curr_avatar) if curr_avatar in AVATAR_OPTIONS else 0)
            col_av2, col_av3 = st.columns(2)
            with col_av2:
                curr_border, border_keys, border_vals = profile.get("avatar_border", "solid"), list(BORDER_STYLE_OPTIONS.keys()), list(BORDER_STYLE_OPTIONS.values())
                selected_border_label = st.selectbox("Avatar Border", border_keys, index=border_vals.index(curr_border) if curr_border in border_vals else 0)
                new_border = BORDER_STYLE_OPTIONS[selected_border_label]
            with col_av3:
                new_av_color = st.color_picker("Avatar Box Color", value=profile.get("avatar_color", "#1e3a8a"))
            new_fav_player = st.text_input("Favorite NFL Player", value=profile.get("favorite_player", ""))
            new_bio = st.text_input("Profile Catchphrase / Bio (max 100 chars)", value=profile.get("bio", "Ready for Kickoff!"), max_chars=100)
            if st.form_submit_button("Save Profile Settings 💾", type="primary"):
                if not new_display_name.strip():
                    st.error("Display Name cannot be blank.")
                elif contains_profanity(new_display_name) or contains_profanity(new_fav_player) or contains_profanity(new_bio):
                    st.error("⚠️ Your profile input contains restricted language. Please choose appropriate wording.")
                else:
                    supabase.table("profiles").update({"full_name": new_display_name.strip(), "favorite_team": new_team, "selected_title": new_title, "avatar_emoji": new_avatar, "avatar_border": new_border, "avatar_color": new_av_color, "favorite_player": new_fav_player.strip(), "bio": new_bio.strip()}).eq("id", user_id).execute()
                    st.success("Profile updated successfully!")
                    st.rerun()

        if locked_title_info:
            st.write("")
            with st.expander("🔒 Locked Nametag Titles & How to Unlock Them"):
                st.caption("Complete achievements and unlock badges to add these titles to your selectable collection!")
                for l_title, l_req in locked_title_info:
                    st.markdown(f"• **{l_title}** — *Requirement:* {l_req}")

        st.divider()
        st.subheader("⭐ Featured Badge Showcase")
        st.caption("Choose up to 3 unlocked badges to showcase on your leaderboard card.")
        unlocked_badges = sync_and_get_user_badges(supabase, user_id)
        valid_current_featured = [b for b in (profile.get("featured_badges", []) if isinstance(profile.get("featured_badges", []), list) else []) if b in unlocked_badges]
        
        with st.form("featured_badges_form"):
            selected_featured = st.multiselect("Select up to 3 Badges to Showcase", options=unlocked_badges, default=valid_current_featured, max_selections=3)
            if st.form_submit_button("Save Featured Badges 🌟", type="primary"):
                supabase.table("profiles").update({"featured_badges": selected_featured}).eq("id", user_id).execute()
                st.success("Featured badges updated successfully!")
                st.rerun()

        st.divider()
        st.subheader("🏆 Virtual Trophy Cabinet")
        st.caption("Inspect badge showcases across any league member.")
        all_league_profiles = get_cached_profiles()
        user_name_map = {p["full_name"]: p for p in all_league_profiles}
        default_profile_name = profile.get("full_name", list(user_name_map.keys())[0] if user_name_map else "")
        
        st.markdown("**Select Player Trophy Showcase:**")
        selected_player_name = st.selectbox("Select Player Trophy Showcase", list(user_name_map.keys()), index=list(user_name_map.keys()).index(default_profile_name) if default_profile_name in user_name_map else 0, key="trophy_player_select", label_visibility="collapsed")
        selected_player = user_name_map[selected_player_name]
        selected_badges = sync_and_get_user_badges(supabase, user_id) if selected_player["id"] == user_id else selected_player.get("unlocked_badges") or []
        selected_team_info = NFL_TEAM_DATA.get(selected_player.get("favorite_team"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
        
        progress_ratio = len(selected_badges) / len(MASTER_BADGES)
        col_t_logo, col_t_info = st.columns([1, 4])
        with col_t_logo:
            st.image(selected_team_info["logo"], width=70)
        with col_t_info:
            st.markdown(f"### {selected_player.get('avatar_emoji', '🏈')} {selected_player['full_name']}'s Showcase")
            st.markdown(f"**Unlocked:** `{len(selected_badges)}` / `{len(MASTER_BADGES)}` Badges")
        st.progress(progress_ratio, text=f"**Cabinet Completion:** `{int(progress_ratio * 100)}%` Unlocked")
        st.write("")

        t_col1, t_col2 = st.columns(2)
        for idx, (b_name, b_desc) in enumerate(MASTER_BADGES.items()):
            with (t_col1 if idx % 2 == 0 else t_col2):
                if b_name in selected_badges:
                    st.markdown(f"""<div class="trophy-card-unlocked"><b>{b_name}</b> <span style="color:#fbbf24; font-weight:bold;">(UNLOCKED)</span><br><small style="color:#cbd5e1;">{b_desc}</small></div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class="trophy-card-locked"><b>🔒 {b_name}</b><br><small>{b_desc}</small></div>""", unsafe_allow_html=True)

    with tab_rules:
        st.markdown("## 📖 Rules & Information Hub\nEverything you need to know about dominating Touchdown Tokens.\n")
        st.markdown(f"""<div class="rule-card"><div class="rule-step-num">01 / THE CORE PREMISE</div><div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">10 Scenarios. Cumulative Tokens. High Stakes.</div><p style="color: #cbd5e1; line-height: 1.6; margin: 0;">Each week brings 10 custom NFL scenarios. Every player starts with 10 tokens. When you win a bet, your wagered tokens double! Lose a bet, and those wagered tokens are lost. Your token bank is cumulative across the entire season—build a massive lead or claw your way back from zero.</p></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="rule-card"><div class="rule-step-num">02 / TOUCHDOWN SCORER BONUS</div><div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">The Free Weekly Scorer Pick (+5 Tokens)</div><p style="color: #cbd5e1; line-height: 1.6; margin: 0;">At the bottom of your weekly slate, you can name 1 player to score a touchdown. If your chosen player rushes or receives a touchdown, you instantly pocket <b style="color: {user_team_color};">+5 bonus tokens</b> for the next week! <i>Note: Passing touchdowns do not count.</i></p></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="rule-card"><div class="rule-step-num">03 / SCHEDULE & CUTOFFS</div><div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Sunday & Monday Slates Only</div><p style="color: #cbd5e1; line-height: 1.6; margin: 0;">All scenarios feature Sunday or Monday games (no Thursday night fixtures). Submissions automatically lock down precisely <b style="color: #38bdf8;">15 minutes before the first Sunday kickoff</b>. Make sure your lock-ins are saved before time expires!</p></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="rule-card"><div class="rule-step-num">04 / IMPORTANT LEAGUE POLICIES</div><div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Fair Play, Overrides & Inactive Scratches</div><ul style="color: #cbd5e1; padding-left: 20px; line-height: 1.6; margin: 0;"><li><b>Submissions & Overrides:</b> You can update your picks and wagers as many times as you like before the kickoff deadline. <b>Your final submit will be your real one and it will completely override your previous picks!</b></li><li><b>Submitting with 0 Wagers:</b> Even if you don't want to risk any tokens on a specific question, you can still submit your Yes/No answer with a <b>0 token wager</b> to test your predictions and see how you would have performed!</li><li><b>Late Scratches:</b> If a specific player mentioned in a scenario is ruled out before kickoff, bets on that scenario are fully refunded.</li><li><b>Missed Weeks:</b> Taking a week off is totally fine, though consistent consecutive absences may incur point deductions.</li><li><b>One Choice Per Question:</b> Lock in either Yes or No per matchup.</li></ul></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="rule-card" style="border-top-color: #38bdf8;"><div class="rule-step-num" style="color: #38bdf8;">📱 PRO TIP / MOBILE ACCESS</div><div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Add Touchdown Tokens to Your Phone Home Screen</div><p style="color: #cbd5e1; line-height: 1.6; margin-bottom: 12px;">Treat this app like a native mobile app for instant access on game days:</p><div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;"><div style="background: rgba(15,23,42,0.6); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);"><b style="color: #38bdf8;">🍎 iPhone (Safari):</b><br>Tap the <i>Share Button</i> at the bottom → Select <b>'Add to Home Screen'</b>.</div><div style="background: rgba(15,23,42,0.6); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);"><b style="color: #38bdf8;">🤖 Android (Chrome):</b><br>Tap the <i>3 Dots Menu</i> at top right → Select <b>'Install App'</b> or <b>'Add to Home Screen'</b>.</div></div></div>""", unsafe_allow_html=True)
        st.write("")
        with st.expander("❓ Frequently Asked Questions (FAQ)"):
            st.markdown("""### 📋 General & Gameplay FAQs\n\n**Q: What happens if an NFL game is postponed or canceled?**\n*A:* Any scenario connected to a game that is postponed or canceled is automatically voided, and all tokens wagered on that scenario are fully refunded to your bank.\n\n**Q: Can I submit my picks without wagering any tokens?**\n*A:* Yes! Even if you don't want to risk any tokens on a question, you can lock in your Yes/No pick with a **0 token wager**. This lets you participate, test your predictions, and track how well you would have done without risking your bank balance.\n\n**Q: Can I change my picks after submitting them?**\n*A:* Yes, you can submit new picks and wagers as many times as you like before the kickoff lockout. **Your final submit will be your real one and it will completely override your previous picks.**\n\n**Q: How does the Touchdown Scorer bonus work?**\n*A:* You can name any player to score a rushing or receiving touchdown. Passing touchdowns do not count. If your selected player scores, you pocket **+5 bonus tokens** for the following week!\n\n**Q: What is a "Nemesis" on the leaderboard?**\n*A:* Your Nemesis is the player in your selected league whom you disagreed with the most on weekly bets where they ended up winning points at your expense!\n\n**Q: How do I unlock prestigious nametag titles?**\n*A:* Titles like *The Oracle*, *Token Tycoon*, and *Gridiron Prophet* unlock automatically as you achieve milestone records or unlock specific badges in your Virtual Trophy Cabinet. Once unlocked, you can select them from your **Profile** tab!\n\n**Q: What happens if my token balance drops to 0?**\n*A:* Don't worry! Reaching 0 tokens unlocks the *Down Bad* badge and title, but you can always bounce back in future weeks through the Touchdown Scorer bonus or special league events.""")

    with tab_bet:
        st.markdown(f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><div><h2 style="font-family: 'Bebas Neue', sans-serif; font-size: 38px; color: #ffffff; letter-spacing: 2px; margin: 0;">WEEKLY PREDICTIONS & WAGERS</h2><p style="color: #94a3b8; font-size: 14px; margin: 0;">Review matchups, lock in your predictions, and assign your token stakes.</p></div><div><a href="https://www.espn.com/nfl/schedule" target="_blank" style="display: inline-flex; align-items: center; gap: 8px; background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(255, 255, 255, 0.2); border-left: 4px solid #38bdf8; color: #ffffff !important; padding: 10px 18px; border-radius: 12px; font-family: 'Teko', sans-serif; font-size: 20px; letter-spacing: 1.2px; text-decoration: none !important; box-shadow: 0 4px 15px rgba(0,0,0,0.4); transition: all 0.2s ease;">🏈 ESPN Scoreboard <span style="font-size: 14px; color: #38bdf8;">↗</span></a></div></div>""", unsafe_allow_html=True)
        if not available_weeks:
            st.info("No active questions available yet. Check back soon when the Admin posts Week 1!")
        else:
            active_unscored_weeks = []
            for w in available_weeks:
                week_status_row = supabase.table("weekly_questions").select("winning_answer").eq("week_number", w).eq("question_number", 96).execute().data
                is_closed = week_status_row and week_status_row[0]["winning_answer"] == "CLOSED"
                if not is_closed:
                    w_qs_check = supabase.table("weekly_questions").select("winning_answer").eq("week_number", w).neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
                    if w_qs_check and all(q["winning_answer"] in ["Yes", "No"] for q in w_qs_check):
                        is_closed = True
                if not is_closed:
                    active_unscored_weeks.append(w)
            
            if not active_unscored_weeks:
                st.info("🎉 All currently available weeks have been graded and closed! Check back when the Admin posts a new active week.")
            else:
                selected_week = st.selectbox("Select Week:", active_unscored_weeks, index=len(active_unscored_weeks) - 1)
                questions = get_cached_weekly_questions(selected_week)
                is_locked = False
                lock_time_row = [q for q in questions if q.get("winning_answer", "").startswith("LOCKTIME:")]
                if lock_time_row:
                    try:
                        lock_dt = datetime.fromisoformat(lock_time_row[0]["winning_answer"].replace("LOCKTIME:", "")).replace(tzinfo=timezone.utc)
                        total_seconds_left = int((lock_dt - datetime.now(timezone.utc)).total_seconds())
                        if total_seconds_left <= 0:
                            is_locked = True
                            st.error("🔒 Entries for this week are locked! Kickoff deadline has passed.")
                        else:
                            days, remainder = divmod(total_seconds_left, 86400)
                            hours, remainder = divmod(remainder, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            st.markdown(f"""<div class="timer-card">⏳ <b>KICKOFF LOCKOUT COUNTDOWN:</b> <span style="font-size:20px; font-weight:bold; color:{user_team_color};">{f'{days}d ' if days>0 else ''}{hours}h {minutes}m {seconds}s remaining</span></div>""", unsafe_allow_html=True)
                    except Exception:
                        pass
                
                if any(q.get("winning_answer") == "LOCKED" for q in questions):
                    is_locked = True
                    st.error("🔒 Entries for this week have been manually locked by the Admin.")
                
                if not questions:
                    st.info("No questions found for this week.")
                else:
                    true_global_tokens_bet = get_true_global_token_balance(user_id)
                    if not is_locked and true_global_tokens_bet > 0:
                        col_rand_sp1, col_rand_btn = st.columns([3, 1])
                        with col_rand_btn:
                            if st.button("🎲 Feeling Lucky (Randomize)", help="Randomly distributes your available tokens and picks across the questions!"):
                                with st.spinner("🎲 Simulating lucky picks and distributing tokens..."):
                                    real_q_items = [q for q in questions if not q.get("winning_answer", "").startswith("LOCKTIME:")]
                                    if real_q_items:
                                        supabase.table("user_bets").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
                                        token_allocations = {q["id"]: 0 for q in real_q_items}
                                        for _ in range(true_global_tokens_bet):
                                            token_allocations[random.choice(real_q_items)["id"]] += 1
                                        for q_item in real_q_items:
                                            supabase.table("user_bets").insert({"user_id": user_id, "user_name": profile["full_name"], "week_number": selected_week, "question_id": q_item["id"], "pick": random.choice(["Yes", "No"]), "wager_amount": token_allocations[q_item["id"]]}).execute()
                                        st.cache_data.clear()
                                        st.session_state.form_refresh += 1
                                        st.success("🎲 Random bets generated and populated successfully!")
                                        st.rerun()

                    all_week_bets = supabase.table("user_bets").select("question_id, pick, wager_amount").eq("user_id", user_id).eq("week_number", selected_week).execute().data
                    existing_bets_map = {b["question_id"]: b for b in all_week_bets}
                    existing_td = supabase.table("touchdown_picks").select("player_name").eq("user_id", user_id).eq("week_number", selected_week).execute().data
                    default_td = existing_td[0]["player_name"] if existing_td else ""

                    with st.form("weekly_bet_form"):
                        wagers, picks = {}, {}
                        st.markdown("""<div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%); border: 1px solid rgba(255,255,255,0.1); border-left: 4px solid #fbbf24; padding: 14px 18px; border-radius: 12px; margin-bottom: 20px;"><b style="color: #fff; font-size: 15px;">MATCHUP PREDICTION SLATE</b><p style="color: #94a3b8; font-size: 13px; margin: 4px 0 0 0;">Matchup cards are expanded by default so you can easily review and configure your picks and token stakes.</p></div>""", unsafe_allow_html=True)
                        
                        for q in questions:
                            if q.get("winning_answer", "").startswith("LOCKTIME:"):
                                continue
                            full_q_text = q["question_text"]
                            away_team_name = home_team_name = "🏈 Free Agent / Neutral"
                            prompt_text = full_q_text
                            if " | MATCHUP: " in full_q_text:
                                prompt_text, matchup_str = full_q_text.split(" | MATCHUP: ")
                                if " @ " in matchup_str:
                                    away_team_name, home_team_name = matchup_str.split(" @ ")
                            
                            away_info, home_info = NFL_TEAM_DATA.get(away_team_name, NFL_TEAM_DATA["🏈 Free Agent / Neutral"]), NFL_TEAM_DATA.get(home_team_name, NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
                            prev_bet = existing_bets_map.get(q["id"], {})
                            default_pick_val, default_wager_val = prev_bet.get("pick", "Yes"), prev_bet.get("wager_amount", 0)
                            
                            with st.expander(f"Matchup Q{q['question_number']}: {away_team_name} @ {home_team_name} (Wager: {default_wager_val} 🪙)", expanded=True):
                                st.markdown(f"""<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 10px; background: rgba(30, 41, 59, 0.4); border-radius: 10px;"><img src="{away_info['logo']}" style="width: 24px; height: 24px;" /><span style="font-size: 13px; color: #cbd5e1; font-weight: bold;">{away_team_name}</span><span style="color: #64748b;">@</span><img src="{home_info['logo']}" style="width: 24px; height: 24px;" /><span style="font-size: 13px; color: #cbd5e1; font-weight: bold;">{home_team_name}</span></div><div style="font-size: 15px; font-weight: 600; color: #ffffff; margin-bottom: 14px; line-height: 1.4;">{prompt_text}</div>""", unsafe_allow_html=True)
                                col_pick, col_wager = st.columns(2)
                                with col_pick:
                                    picks[q["id"]] = st.radio(f"Pick Q{q['question_number']}", ["Yes", "No"], index=0 if default_pick_val == "Yes" else 1, key=f"pick_w{selected_week}_{q['id']}_{st.session_state.form_refresh}", horizontal=True, disabled=is_locked, label_visibility="collapsed")
                                with col_wager:
                                    wagers[q["id"]] = st.number_input(f"Wager Q{q['question_number']} Tokens", min_value=0, max_value=true_global_tokens_bet, value=default_wager_val, key=f"wager_w{selected_week}_{q['id']}_{st.session_state.form_refresh}", disabled=is_locked)

                        st.markdown(f"""<div style="background: linear-gradient(135deg, rgba(30, 58, 138, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%); border: 1px solid rgba(255,255,255,0.1); border-left: 4px solid #38bdf8; padding: 14px 18px; border-radius: 12px; margin: 20px 0 14px 0;"><b style="color: #fff; font-size: 15px;">🏈 BONUS TOUCHDOWN SCORER</b><p style="color: #94a3b8; font-size: 13px; margin: 4px 0 0 0;">Name 1 player to score a touchdown this week (rushing/receiving only). Correct pick yields +5 bonus tokens!</p></div>""", unsafe_allow_html=True)
                        td_pick = st.text_input("Player Name (e.g., Patrick Mahomes)", value=default_td, key=f"td_scorer_w{selected_week}_{st.session_state.form_refresh}", disabled=is_locked, label_visibility="collapsed")
                        total_wagered = sum(wagers.values())
                        
                        if total_wagered > true_global_tokens_bet:
                            st.error(f"⚠️ Over-wagered! You have allocated {total_wagered} tokens but only have {true_global_tokens_bet} available.")
                        else:
                            st.progress(min(1.0, total_wagered / max(1, true_global_tokens_bet)), text=f"**Tokens Allocated:** `{total_wagered}` / `{true_global_tokens_bet}` Tokens ({int(min(1.0, total_wagered / max(1, true_global_tokens_bet)) * 100)}%)")
                        st.caption("💡 *Tip: Remember that even if you don't want to risk tokens on a question, you can set the wager to 0 tokens to submit your answer and test how you would have done!*")
                        
                        col_sub1, col_sub2 = st.columns([2, 1])
                        with col_sub1:
                            submit_bet = st.form_submit_button("Submit Weekly Bets 🚀", type="primary", disabled=is_locked)
                        with col_sub2:
                            clear_bet = st.form_submit_button("Clear Bet Choices 🗑️", disabled=is_locked)

                        if clear_bet and not is_locked:
                            supabase.table("user_bets").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
                            supabase.table("touchdown_picks").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
                            st.session_state.form_refresh += 1
                            st.success("Your bet choices for this week have been cleared!")
                            st.rerun()

                        if submit_bet and not is_locked:
                            if contains_profanity(td_pick):
                                st.error("⚠️ Your Touchdown Scorer player pick contains restricted language. Please choose a valid player name.")
                            elif total_wagered > true_global_tokens_bet:
                                st.error(f"Cannot wager {total_wagered} tokens! You only have {true_global_tokens_bet} tokens available.")
                            else:
                                for q_id, pick_val in picks.items():
                                    supabase.table("user_bets").delete().eq("user_id", user_id).eq("question_id", q_id).execute()
                                    supabase.table("user_bets").insert({"user_id": user_id, "user_name": profile["full_name"], "week_number": selected_week, "question_id": q_id, "pick": pick_val, "wager_amount": wagers[q_id]}).execute()
                                if td_pick:
                                    supabase.table("touchdown_picks").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
                                    supabase.table("touchdown_picks").insert({"user_id": user_id, "week_number": selected_week, "player_name": td_pick, "is_correct": None}).execute()
                                st.balloons()
                                st.success("Your bets and touchdown pick have been successfully locked in!")

    with tab_history:
        st.header("📜 Your Past Bets & Results")
        st.caption("Review your historical predictions, weekly outcomes, and track your performance over time.")
        all_graded_weeks_res, graded_weeks_set = get_cached_all_weekly_questions_meta(), set()
        closed_markers = supabase.table("weekly_questions").select("week_number").eq("question_number", 96).eq("winning_answer", "CLOSED").execute().data
        if closed_markers:
            [graded_weeks_set.add(cm["week_number"]) for cm in closed_markers]
        if all_graded_weeks_res:
            week_ans_map = {}
            for q in all_graded_weeks_res:
                if q["week_number"] not in week_ans_map:
                    week_ans_map[q["week_number"]] = []
                if q.get("question_number", 0) <= 10:
                    week_ans_map[q["week_number"]].append(q["winning_answer"])
            [graded_weeks_set.add(w) for w, ans_list in week_ans_map.items() if ans_list and all(a in ["Yes", "No"] for a in ans_list)]
        
        graded_weeks_list = sorted(list(graded_weeks_set))
        st.subheader("🏈 Touchdown Scorer Pick History")
        st.caption("Review your bonus touchdown scorer pick outcomes week by week.")
        all_td_picks = supabase.table("touchdown_picks").select("*").eq("user_id", user_id).order("week_number").execute().data
        if all_td_picks:
            td_history_rows = [{"Week": f"Week {td['week_number']}", "Touchdown Scorer Pick": td["player_name"], "Result": "⏳ Pending (Awaiting Admin Grading)" if td.get("is_correct") is None else "✅ Correct (+5 Bonus Tokens)" if str(td.get("is_correct")).lower() == "true" else "❌ Incorrect (Missed)"} for td in all_td_picks]
            st.dataframe(pd.DataFrame(td_history_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No touchdown scorer picks submitted yet.")

        st.divider()
        st.subheader("📋 Detailed Question Bet History")
        history_bets = supabase.table("user_bets").select("*, weekly_questions(week_number, question_number, question_text, winning_answer)").eq("user_id", user_id).execute().data
        if not history_bets:
            st.info("You haven't placed any question bets yet.")
        else:
            user_history_weeks = sorted(list(set([b["week_number"] for b in history_bets])))
            selected_history_week = st.selectbox("Filter History by Week", user_history_weeks, index=len(user_history_weeks) - 1, key="history_week_dropdown_filter")
            st.write("")
            filtered_history_bets = [b for b in history_bets if b["week_number"] == selected_history_week]
            if not filtered_history_bets:
                st.info(f"No bets found for Week {selected_history_week}.")
            else:
                formatted_data = []
                for b in filtered_history_bets:
                    q_info, pick = b.get("weekly_questions", {}), b["pick"]
                    w_ans, raw_q_text, q_num = q_info.get("winning_answer", "Pending"), q_info.get("question_text", "N/A"), q_info.get("question_number", "?")
                    clean_q_prompt = raw_q_text.split(" | MATCHUP: ")[0] if " | MATCHUP: " in raw_q_text else raw_q_text
                    outcome = "⏳ Pending" if w_ans in ["Pending", "LOCKED"] or w_ans.startswith("LOCKTIME:") else f"✅ Won (+{b['wager_amount']} 🪙 Net)" if pick == w_ans else f"❌ Lost (-{b['wager_amount']} 🪙)"
                    formatted_data.append({"Q#": f"Q{q_num}", "Question": clean_q_prompt, "Your Pick": pick, "Wager": f"{b['wager_amount']} 🪙", "Winner": "Pending" if w_ans.startswith("LOCKTIME:") or w_ans in ["Pending", "LOCKED"] else w_ans, "Outcome": outcome})
                st.dataframe(pd.DataFrame(formatted_data), use_container_width=True, hide_index=True, column_config={"Q#": st.column_config.TextColumn("Q#", width="small"), "Question": st.column_config.TextColumn("Question", width="large"), "Your Pick": st.column_config.TextColumn("Your Pick", width="small"), "Wager": st.column_config.TextColumn("Wager", width="small"), "Winner": st.column_config.TextColumn("Winner", width="small"), "Outcome": st.column_config.TextColumn("Outcome", width="medium")})

        st.divider()
        with st.expander("⚔️ Side-by-Side History Comparison vs. Rival", expanded=False):
            st.caption("Compare your graded week bets side by side against any member in your leagues in a clean head-to-head match card format!")
            my_league_ids = [m["league_id"] for m in supabase.table("league_members").select("league_id").eq("user_id", user_id).execute().data or []]
            league_peers_res = supabase.table("league_members").select("user_id, profiles(id, full_name, favorite_team, avatar_emoji)").in_("league_id", my_league_ids).execute().data
            rival_options = {lp.get("profiles")["full_name"]: lp.get("profiles") for lp in league_peers_res if lp.get("profiles") and lp.get("profiles")["id"] != user_id} if league_peers_res else {}

            if rival_options and graded_weeks_list:
                col_comp_w, col_comp_r = st.columns(2)
                with col_comp_w:
                    comp_week_sel = st.selectbox("Select Graded Week for Comparison", graded_weeks_list, key="hist_comp_week")
                with col_comp_r:
                    comp_rival_name = st.selectbox("Select Rival (Shared League Member)", list(rival_options.keys()), key="hist_comp_rival")
                rival_prof = rival_options[comp_rival_name]
                
                my_hist_bets = supabase.table("user_bets").select("question_id, pick, wager_amount, weekly_questions(question_number, question_text, winning_answer)").eq("user_id", user_id).eq("week_number", comp_week_sel).order("question_id").execute().data
                rival_hist_bets = supabase.table("user_bets").select("question_id, pick, wager_amount").eq("user_id", rival_prof["id"]).eq("week_number", comp_week_sel).execute().data
                rival_bets_map = {b["question_id"]: (b["pick"], b["wager_amount"]) for b in rival_hist_bets}

                if my_hist_bets:
                    st.write("")
                    rival_team_info = NFL_TEAM_DATA.get(rival_prof.get("favorite_team"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
                    st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid {rival_team_info['color']}; padding: 12px 18px; border-radius: 12px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;"><div style="display: flex; align-items: center; gap: 10px;"><span style="font-size: 24px;">{rival_prof.get("avatar_emoji", "🏈")}</span><div><b style="color: #fff; font-size: 16px;">Head-to-Head: Week {comp_week_sel} Matchup</b><div style="font-size: 12px; color: #94a3b8;">{profile['full_name']} vs. {comp_rival_name}</div></div></div><img src="{rival_team_info['logo']}" style="width: 32px; height: 32px;" /></div>""", unsafe_allow_html=True)
                    
                    for b in my_hist_bets:
                        q_info = b.get("weekly_questions", {})
                        raw_q, w_ans = q_info.get("question_text", "N/A"), q_info.get("winning_answer", "")
                        clean_q = raw_q.split(" | MATCHUP: ")[0] if " | MATCHUP: " in raw_q else raw_q
                        my_pick, my_wager = b["pick"], b["wager_amount"]
                        riv_pick, riv_wager = rival_bets_map.get(b["question_id"], ("Did Not Bet", 0))
                        my_won, riv_won = my_pick == w_ans, riv_pick == w_ans

                        my_pill_bg, my_pill_border, my_pill_color, my_status_text = ("rgba(16, 185, 129, 0.18)", "#10b981", "#34d399", f"Won (+{my_wager}🪙 Net)") if my_won else ("rgba(239, 68, 68, 0.18)", "#ef4444", "#f87171", f"Lost (-{my_wager}🪙)")
                        if riv_pick in ["Yes", "No"]:
                            riv_pill_bg, riv_pill_border, riv_pill_color, riv_status_text = ("rgba(16, 185, 129, 0.18)", "#10b981", "#34d399", f"Won (+{riv_wager}🪙 Net)") if riv_won else ("rgba(239, 68, 68, 0.18)", "#ef4444", "#f87171", f"Lost (-{riv_wager}🪙)")
                        else:
                            riv_pill_bg, riv_pill_border, riv_pill_color, riv_status_text = "rgba(100, 116, 139, 0.2)", "#64748b", "#94a3b8", "Did Not Bet"

                        st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 16px; margin-bottom: 14px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;"><span style="font-family: 'Bebas Neue'; font-size: 20px; color: {user_team_color}; letter-spacing: 1px;">QUESTION {q_info.get('question_number', '?')}</span><span style="font-size: 13px; color: #cbd5e1; background: rgba(255,255,255,0.08); padding: 2px 10px; border-radius: 8px;">Official Winner: <b style="color: #38bdf8;">{w_ans}</b></span></div><div style="font-size: 15px; font-weight: 600; color: #ffffff; margin-bottom: 12px; line-height: 1.4;">{clean_q}</div><div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;"><div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 10px 12px;"><div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">You ({profile['full_name']})</div><div style="display: flex; justify-content: space-between; align-items: center;"><span style="font-size: 15px; font-weight: 700; color: #fff;">Pick: <span style="color: {user_team_color};">{my_pick}</span> ({my_wager}🪙)</span><span style="font-size: 12px; font-weight: 600; background: {my_pill_bg}; border: 1px solid {my_pill_border}; color: {my_pill_color}; padding: 2px 8px; border-radius: 6px;">{my_status_text}</span></div></div><div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 10px 12px;"><div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">{comp_rival_name}</div><div style="display: flex; justify-content: space-between; align-items: center;"><span style="font-size: 15px; font-weight: 700; color: {rival_team_info['color']};">Pick: {riv_pick} ({riv_wager}🪙)</span><span style="font-size: 12px; font-weight: 600; background: {riv_pill_bg}; border: 1px solid {riv_pill_border}; color: {riv_pill_color}; padding: 2px 8px; border-radius: 6px;">{riv_status_text}</span></div></div></div></div>""", unsafe_allow_html=True)
                else:
                    st.info("You did not place any bets for this selected comparison week.")
            else:
                st.info("Side-by-side historical comparison will unlock here automatically once at least one week has been fully graded by the Admin and you share a league with other active participants!")

    with tab_leagues:
        st.header("🏆 League Standings & Mini-Leagues")
        st.caption("Track your standings across the Global Leaderboard and your custom mini-leagues. Your Nemesis is tracked exclusively within the selected league!")
        my_memberships = supabase.table("league_members").select("league_id, leagues(id, league_name, invite_code, created_by)").eq("user_id", user_id).execute().data
        all_my_leagues = [m for m in my_memberships if m.get("leagues")]
        
        league_filter_options = {}
        if next((m for m in all_my_leagues if m["leagues"]["id"] == "00000000-0000-0000-0000-000000000001"), None):
            league_filter_options["🏆 Global Leaderboard"] = "00000000-0000-0000-0000-000000000001"
        for m in [m for m in all_my_leagues if m["leagues"]["id"] != "00000000-0000-0000-0000-000000000001"]:
            league_filter_options[f"🛡️ {m['leagues']['league_name']} (Mini-League)"] = m['leagues']['id']

        if league_filter_options:
            default_label = next((k for k, v in league_filter_options.items() if v == profile.get("default_league_view", "00000000-0000-0000-0000-000000000001")), list(league_filter_options.keys())[0])
            selected_league_filter_label = st.selectbox("Select Standings View", list(league_filter_options.keys()), index=list(league_filter_options.keys()).index(default_label) if default_label in league_filter_options else 0, key="unified_league_view_selector")
            selected_league_filter_id = league_filter_options[selected_league_filter_label]
            st.write("")
            
            is_global_view = selected_league_filter_id == "00000000-0000-0000-0000-000000000001"
            clean_display_name = selected_league_filter_label.replace("🛡️ ", "").replace("🏆 ", "").replace(" (Mini-League)", "")
            st.subheader(f"{'🏆' if is_global_view else '🛡️'} {clean_display_name} Standings")
            
            allowed_peer_ids = None if is_global_view else {cm["user_id"] for cm in supabase.table("league_members").select("user_id").eq("league_id", selected_league_filter_id).execute().data or []}
            filtered_player_stats = get_cached_leaderboard_stats(allowed_peer_ids=allowed_peer_ids)

            if not filtered_player_stats:
                st.info("No players found in this standings view yet.")
            else:
                def render_player_row(p, current_rank_val):
                    t_info = NFL_TEAM_DATA.get(p.get("favorite_team"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
                    showcased = p.get("featured_badges") or []
                    if not showcased or not isinstance(showcased, list):
                        showcased = p.get("unlocked_badges", [])[:2]
                    badges_str = " • ".join(showcased) if showcased else "No Badges"
                    
                    podium_class, rank_display = "leaderboard-row", f"#{current_rank_val}"
                    if current_rank_val == 1:
                        podium_class += " podium-rank-1"
                        rank_display = "🥇 1"
                    elif current_rank_val == 2:
                        podium_class += " podium-rank-2"
                        rank_display = "🥈 2"
                    elif current_rank_val == 3:
                        podium_class += " podium-rank-3"
                        rank_display = "🥉 3"

                    st.markdown(f"""<div class="{podium_class}"><div style="display: flex; align-items: center; gap: 10px; overflow: hidden;"><span style="font-family: 'Bebas Neue'; font-size: 18px; color: #fbbf24; min-width: 26px;">{rank_display}</span><div style="border: 2px {p.get('avatar_border') or 'solid'} {t_info['color']}; border-radius: 6px; padding: 1px 5px; background: {p.get('avatar_color') or '#1e3a8a'}; flex-shrink: 0;"><span style="font-size: 15px;">{p.get('avatar_emoji') or '🏈'}</span></div><div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><b style="font-size: 13px; color: #ffffff;">{p['full_name']}</b> <span style="font-size: 9px; color: #38bdf8;">[{get_earned_title(supabase, p['id'])}]</span><div class="stat-pill-container"><span class="stat-pill">🪙 <b>{p['tokens']}</b></span><span class="stat-pill">🎯 {p['win_rate']}%</span><span class="stat-pill">🏈 {p['correct_tds']} TDs</span><span class="stat-pill">🔥 {p['streak']}</span><span class="stat-pill" style="color: #94a3b8; max-width: 130px; overflow: hidden; text-overflow: ellipsis;">🏆 {badges_str}</span></div></div></div><div style="text-align: right; flex-shrink: 0; margin-left: 8px;"><span style="font-family: 'Bebas Neue'; font-size: 20px; color: #38bdf8;">{p['tokens']} 🪙</span></div></div>""", unsafe_allow_html=True)

                current_rank, prev_score, prev_tds, all_ranked_players = 1, None, None, []
                for idx, p in enumerate(filtered_player_stats):
                    score, tds = p["tokens"], p["correct_tds"]
                    if not (idx > 0 and score == prev_score and tds == prev_tds):
                        current_rank = idx + 1
                    prev_score, prev_tds = score, tds
                    all_ranked_players.append((p, current_rank))
                
                if is_global_view:
                    for p_obj, r_num in all_ranked_players[:10]:
                        render_player_row(p_obj, r_num)
                    logged_in_entry = next((item for item in all_ranked_players if item[0]["id"] == user_id), None)
                    if logged_in_entry and logged_in_entry[1] > 10:
                        st.markdown("<div style='text-align:center; color:#94a3b8; margin: 8px 0; font-size: 12px;'>• • • your standing • • •</div>", unsafe_allow_html=True)
                        render_player_row(logged_in_entry[0], logged_in_entry[1])
                else:
                    for p_obj, r_num in all_ranked_players:
                        render_player_row(p_obj, r_num)

            st.divider()

            if not is_global_view:
                with st.expander("⚔️ Head-to-Head Player Comparison", expanded=False):
                    if filtered_player_stats:
                        all_other_names = [p["full_name"] for p in filtered_player_stats if p["id"] != user_id]
                        if all_other_names:
                            compare_name = st.selectbox("Select Rival to Compare Against:", all_other_names, key="leagues_rival_select")
                            my_stat = next((p for p in filtered_player_stats if p["id"] == user_id), filtered_player_stats[0])
                            rival_stat = next((p for p in filtered_player_stats if p["full_name"] == compare_name), filtered_player_stats[0])
                            c1, c2, c3 = st.columns([3, 1, 3])
                            with c1:
                                st.markdown(f"""<div class="vs-card"><h3>{my_stat.get('avatar_emoji', '🏈')} You ({my_stat['full_name']})</h3><h2 style="color: {user_team_color};">{my_stat['tokens']} 🪙</h2><p><b>Title:</b> {get_earned_title(supabase, user_id)}</p><p><b>Win Rate:</b> {my_stat['win_rate']}%</p><p><b>Correct TDs:</b> {my_stat['correct_tds']}</p><p><b>Nemesis:</b> <span style="color:#f87171;">{my_stat['nemesis_name']}</span> ({my_stat['nemesis_score']})</p></div>""", unsafe_allow_html=True)
                            with c2:
                                st.markdown("<h1 style='text-align:center; margin-top:50px;'>VS</h1>", unsafe_allow_html=True)
                            with c3:
                                st.markdown(f"""<div class="vs-card"><h3>{rival_stat.get('avatar_emoji','🏈')} {rival_stat['full_name']}</h3><h2 style="color: {NFL_TEAM_DATA.get(rival_stat.get('favorite_team'), NFL_TEAM_DATA['🏈 Free Agent / Neutral'])['color']};">{rival_stat['tokens']} 🪙</h2><p><b>Title:</b> {get_earned_title(supabase, rival_stat['id'])}</p><p><b>Win Rate:</b> {rival_stat['win_rate']}%</p><p><b>Correct TDs:</b> {rival_stat['correct_tds']}</p><p><b>Nemesis:</b> <span style="color:#f87171;">{rival_stat['nemesis_name']}</span> ({rival_stat['nemesis_score']})</p></div>""", unsafe_allow_html=True)
                        else:
                            st.info("No players available for head-to-head comparison.")
                st.divider()

                with st.expander(f"🏛️ {clean_display_name} Hall of Fame Archives", expanded=False):
                    try:
                        archives_res = supabase.table("archived_seasons").select("season_label, standings_json, archived_at").eq("league_id", selected_league_filter_id).order("archived_at", desc=True).execute().data
                    except Exception:
                        archives_res = []
                    
                    if not archives_res:
                        st.info("No past season archives found yet for this mini-league. Archived seasons will appear here once the commissioner concludes and archives a season!")
                    else:
                        selected_archive_label = st.selectbox("Select Season Archive", [a["season_label"] for a in archives_res], key=f"hof_archive_sel_{selected_league_filter_id}")
                        selected_archive_data = next((a for a in archives_res if a["season_label"] == selected_archive_label), None)
                        if selected_archive_data and selected_archive_data.get("standings_json"):
                            standings_list = selected_archive_data["standings_json"]
                            champ_entry = standings_list[0] if standings_list else {"full_name": "TBD", "tokens": 0}
                            st.markdown(f"""<div class="champion-card"><div style="font-size: 20px; letter-spacing: 2px;">👑 {selected_archive_label.upper()} CHAMPION ({clean_display_name})</div><div style="font-size: 48px; font-weight: 900; margin: 8px 0;">{champ_entry.get('full_name')} ({champ_entry.get('tokens')} 🪙)</div><div style="font-size: 16px;">Crowned the ultimate victor of {clean_display_name}!</div></div>""", unsafe_allow_html=True)
                            formatted_archive_rows = [{"Rank": "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"#{idx+1}", "Player": row.get("full_name", row.get("Player", "Unknown")), "Final Tokens": row.get("tokens", row.get("Final Tokens", 0)), "Favorite Team": row.get("favorite_team", "N/A")} for idx, row in enumerate(standings_list)]
                            st.subheader(f"📜 {selected_archive_label} Official Season Final Standings — {clean_display_name}")
                            st.dataframe(pd.DataFrame(formatted_archive_rows), use_container_width=True, hide_index=True)
                st.divider()

                st.subheader(f"💬 {clean_display_name} Trash Talk Feed")
                with st.form(f"trash_talk_form_{selected_league_filter_id}"):
                    chat_msg = st.text_input("Post a message to this mini-league...", key=f"chat_input_{selected_league_filter_id}")
                    if st.form_submit_button("Post Message 💬") and chat_msg.strip():
                        if contains_profanity(chat_msg):
                            st.error("⚠️ Your message contains restricted language. Please keep chat friendly!")
                        else:
                            try:
                                supabase.table("trash_talk").insert({"user_id": user_id, "message": chat_msg.strip(), "league_id": selected_league_filter_id}).execute()
                                st.success("Message posted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error posting message: {e}")

                recent_chats = supabase.table("trash_talk").select("message, created_at, user_id").eq("league_id", selected_league_filter_id).order("created_at", desc=True).limit(10).execute().data
                if recent_chats:
                    profile_map_chat = {p["id"]: p for p in get_cached_profiles()}
                    for c in recent_chats:
                        p_info = profile_map_chat.get(c["user_id"], {})
                        t_info = NFL_TEAM_DATA.get(p_info.get("favorite_team", "🏈 Free Agent / Neutral"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
                        st.markdown(f"""<div class="chat-bubble" style="border-left: 5px solid {t_info['color']} !important;"><div style="display:flex; align-items:center; gap:8px;"><img src="{t_info['logo']}" style="width:24px; height:24px;" /><b>{p_info.get('avatar_emoji', '🏈')} {p_info.get('full_name', 'Player')}</b> <small style="opacity:0.7;">({p_info.get('favorite_team', '🏈 Free Agent / Neutral')})</small></div><div style="margin-top:4px;">{c['message']}</div></div>""", unsafe_allow_html=True)
                else:
                    st.info("No messages in this mini-league feed yet. Be the first to start the trash talk!")
        st.divider()

        st.subheader("⚙️ Default Standings View")
        st.caption("Configure which league standings view automatically displays when you open the Leagues tab.")
        with st.form("settings_league_tab_form"):
            league_s_options = {"🏆 Global Leaderboard" if m_item["leagues"]["id"] == "00000000-0000-0000-0000-000000000001" else f"🛡️ {m_item['leagues']['league_name']} (Mini-League)": m_item["leagues"]["id"] for m_item in all_my_leagues if m_item.get("leagues")}
            default_keys_list = list(league_s_options.keys())
            def_s_label = next((k for k, v in league_s_options.items() if v == profile.get("default_league_view", "00000000-0000-0000-0000-000000000001")), default_keys_list[0] if default_keys_list else "🏆 Global Leaderboard")
            new_def_league_label = st.selectbox("Default Standings View", default_keys_list, index=default_keys_list.index(def_s_label) if def_s_label in default_keys_list else 0, key="leagues_tab_default_view_select")
            if st.form_submit_button("Save Default View 💾", type="primary"):
                supabase.table("profiles").update({"default_league_view": league_s_options[new_def_league_label]}).eq("id", user_id).execute()
                st.success("Default standings view updated successfully!")
                st.rerun()
        st.divider()

        st.subheader("➕ Create or Join Custom Leagues")
        col_create, col_join = st.columns(2)
        with col_create:
            st.markdown("#### Create a League")
            with st.form("create_league_form"):
                new_league_name = st.text_input("League Name", placeholder="e.g., Office Chumps")
                new_league_pwd = st.text_input("League Password / Passcode (Optional)", type="password", placeholder="Secure access code")
                if st.form_submit_button("Create League 🚀", type="primary"):
                    if not new_league_name.strip():
                        st.error("Please enter a valid league name.")
                    elif contains_profanity(new_league_name):
                        st.error("⚠️ League name contains restricted language. Please choose appropriate wording.")
                    else:
                        import random as r_mod, string as s_mod
                        invite_code = "".join(r_mod.choices(s_mod.ascii_uppercase + s_mod.digits, k=6))
                        try:
                            res_l = supabase.table("leagues").insert({"league_name": new_league_name.strip(), "invite_code": invite_code, "created_by": user_id, "league_password": new_league_pwd.strip() if new_league_pwd else ""}).execute()
                            if res_l.data:
                                supabase.table("league_members").insert({"league_id": res_l.data[0]["id"], "user_id": user_id}).execute()
                                st.success(f"League '{new_league_name}' created successfully! Invite Code: **{invite_code}**")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error creating league: {e}")

        with col_join:
            st.markdown("#### Join a League")
            with st.form("join_league_form"):
                code_input = st.text_input("Enter 6-Character Invite Code", placeholder="e.g., A7X9P2")
                pwd_input = st.text_input("League Password (if required)", type="password", placeholder="Enter password")
                if st.form_submit_button("Join League 🤝", type="primary"):
                    clean_code = code_input.strip().upper()
                    if not clean_code:
                        st.warning("Please enter an invite code.")
                    else:
                        found_league = supabase.table("leagues").select("id, league_name, league_password").eq("invite_code", clean_code).execute().data
                        if not found_league:
                            st.error("Invalid invite code. Please check with your league commissioner.")
                        else:
                            target_league = found_league[0]
                            if target_league.get("league_password", "") and target_league.get("league_password", "") != pwd_input.strip():
                                st.error("Incorrect league password. Please check with the commissioner.")
                            elif supabase.table("league_members").select("id").eq("league_id", target_league["id"]).eq("user_id", user_id).execute().data:
                                st.warning(f"You are already a member of '{target_league['league_name']}'!")
                            else:
                                supabase.table("league_members").insert({"league_id": target_league["id"], "user_id": user_id}).execute()
                                st.success(f"Successfully joined '{target_league['league_name']}'!")
                                st.rerun()

        st.write("")
        st.markdown("#### 📋 Your Joined Mini-Leagues")
        for mem in [m for m in all_my_leagues if m["leagues"]["id"] != "00000000-0000-0000-0000-000000000001"]:
            league_info = mem.get("leagues")
            if league_info:
                members_res = supabase.table("league_members").select("user_id").eq("league_id", league_info["id"]).execute().data
                st.markdown(f"""<div class="summary-box"><div style="display: flex; justify-content: space-between; align-items: center;"><div><h3 style="margin: 0; color: #ffffff;">🛡️ {league_info['league_name']} {'⭐ (You are Commissioner)' if league_info['created_by'] == user_id or profile.get('is_admin', False) else ''}</h3><p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">Invite Code: <b style="color: #38bdf8; letter-spacing: 1px;">{league_info['invite_code']}</b> | Members: <b>{len(members_res) if members_res else 0}</b></p></div></div></div>""", unsafe_allow_html=True)

    with tab_settings:
        st.header("⚙️ Account & App Settings")
        st.caption("Manage your account security, notification preferences, and accessibility options.")
        st.write("")
        st.subheader("🔐 Account Security")
        with st.form("settings_password_form"):
            st.markdown("##### Request Password Reset Email")
            st.caption("Send a secure password reset link directly to your registered email address.")
            if st.form_submit_button("Send Password Reset Email 🔑", type="primary"):
                try:
                    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
                    url = os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
                    admin_supabase = create_client(url, service_key) if service_key and url else supabase
                    response = admin_supabase.auth.admin.generate_link({"type": "recovery", "email": st.session_state.user.email})
                    if response and hasattr(response, "properties") and response.properties:
                        props = response.properties
                        action_link = props.get("action_link") if isinstance(props, dict) else getattr(props, "action_link", None)
                        email_otp = props.get("email_otp") if isinstance(props, dict) else getattr(props, "email_otp", None)
                        recovery_link = f"https://tdtokens.co.uk/?token={email_otp}&type=recovery" if email_otp else (f"https://tdtokens.co.uk/?token={action_link.split('token=')[1].split('&')[0]}&type=recovery" if action_link and "token=" in action_link else action_link)
                        if recovery_link:
                            send_password_reset_email(st.session_state.user.email, recovery_link)
                            st.success("Password reset email sent to your inbox!")
                        else:
                            st.error("Could not retrieve recovery link properties from the response.")
                    else:
                        st.error("Could not generate recovery link for this email.")
                except Exception as e:
                    st.error(f"Error sending password reset email: {e}")

        with st.form("settings_email_form"):
            st.markdown("##### Change Registered Email")
            st.caption(f"Current Email: `{st.session_state.user.email}`")
            new_email_input = st.text_input("New Email Address", key="settings_new_email")
            if st.form_submit_button("Update Email ✉️"):
                if not new_email_input.strip() or "@" not in new_email_input:
                    st.warning("Please enter a valid email address.")
                else:
                    try:
                        supabase.auth.update_user({"email": new_email_input.strip()})
                        supabase.table("profiles").update({"email": new_email_input.strip()}).eq("id", user_id).execute()
                        st.success("Email update requested! Check your new email inbox for confirmation.")
                    except Exception as e:
                        st.error(f"Error updating email: {e}")

        st.divider()
        st.subheader("🔔 Notification Preferences")
        with st.form("settings_notifications_form"):
            new_notif = st.toggle("Enable Email / In-App Result Alerts & Reminders", value=profile.get("email_notifications", True))
            if st.form_submit_button("Save Notification Settings 💾"):
                supabase.table("profiles").update({"email_notifications": new_notif}).eq("id", user_id).execute()
                st.success("Notification preferences saved!")
                st.rerun()

        st.divider()
        st.subheader("♿ Accessibility & Display Preferences")
        with st.form("settings_accessibility_form"):
            new_hc = st.toggle("High Contrast Mode (Enhanced text legibility)", value=profile.get("high_contrast_mode", False))
            new_rm = st.toggle("Reduced Motion (Disable glowing animations & pulses)", value=profile.get("reduced_motion", False))
            if st.form_submit_button("Save Accessibility Settings 💾"):
                supabase.table("profiles").update({"high_contrast_mode": new_hc, "reduced_motion": new_rm}).eq("id", user_id).execute()
                st.success("Accessibility preferences saved!")
                st.rerun()

        st.divider()
        st.subheader("🚪 Session Management")
        st.caption("Log out of your account securely from this device.")
        if st.button("Log Out of Account 🚪", type="secondary"):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            controller.remove("td_tokens_session")
            st.session_state.user = None
            if "supabase_client" in st.session_state:
                del st.session_state["supabase_client"]
            st.rerun()

    if is_any_league_admin:
        with tab_league_admin:
            st.markdown("## ⭐ League Commissioner Administration")
            st.caption("Manage your mini-leagues, update settings, regenerate invite codes, and handle member rosters.")
            st.write("")
            admin_leagues_list = supabase.table("leagues").select("id, league_name, invite_code, league_password, created_by").neq("id", "00000000-0000-0000-0000-000000000001").execute().data if profile.get("is_admin") else my_administered_leagues
            
            if not admin_leagues_list:
                st.info("You are not currently designated as a commissioner for any custom mini-leagues.")
            else:
                league_options_map = {l["league_name"]: l for l in admin_leagues_list}
                selected_league = league_options_map[st.selectbox("Select Mini-League to Administer", list(league_options_map.keys()), key="league_admin_selector_unique")]
                l_id, l_name, l_code, l_pwd_val = selected_league["id"], selected_league["league_name"], selected_league["invite_code"], selected_league.get("league_password", "")
                members_res = supabase.table("league_members").select("user_id, profiles(full_name, tokens, favorite_team)").eq("league_id", l_id).execute().data
                
                st.write("")
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric("League Name", l_name)
                with col_m2:
                    st.metric("Invite Code", l_code)
                with col_m3:
                    st.metric("Total Members", str(len(members_res) if members_res else 0))
                st.write("")

                with st.expander("📝 1. League Settings & Security", expanded=True):
                    with st.form(f"league_settings_form_{l_id}"):
                        new_l_name = st.text_input("League Name", value=l_name, key=f"input_l_name_{l_id}")
                        new_l_pwd = st.text_input("League Password / Passcode (Leave blank for public)", value=l_pwd_val, type="password", placeholder="Secure access code", key=f"input_l_pwd_{l_id}")
                        if st.form_submit_button("Save League Settings 💾", type="primary"):
                            if not new_l_name.strip():
                                st.error("League name cannot be blank.")
                            elif contains_profanity(new_l_name):
                                st.error("⚠️ League name contains restricted language. Please choose appropriate wording.")
                            else:
                                try:
                                    supabase.table("leagues").update({"league_name": new_l_name.strip(), "league_password": new_l_pwd.strip() if new_l_pwd else ""}).eq("id", l_id).execute()
                                    st.cache_data.clear()
                                    st.success("League settings updated successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error updating league settings: {e}")

                with st.expander("👥 2. Roster & Member Removal", expanded=False):
                    st.caption("Remove players from your league roster if necessary.")
                    if members_res:
                        member_names_map = {m.get("profiles", {}).get("full_name", "Unknown"): m["user_id"] for m in members_res if m.get("profiles") and m["user_id"] != user_id}
                        if member_names_map:
                            with st.form(f"kick_form_{l_id}"):
                                target_kick_name = st.selectbox("Select Member to Kick / Remove", list(member_names_map.keys()), key=f"sel_kick_member_{l_id}")
                                confirm_kick = st.checkbox(f"I confirm I want to remove this member from {l_name}", key=f"chk_confirm_kick_{l_id}")
                                if st.form_submit_button("Remove Member from League 🚪", type="secondary"):
                                    if not confirm_kick:
                                        st.warning("Please check the confirmation box to remove the selected member.")
                                    else:
                                        try:
                                            supabase.table("league_members").delete().eq("league_id", l_id).eq("user_id", member_names_map[target_kick_name]).execute()
                                            st.cache_data.clear()
                                            st.success(f"Successfully removed {target_kick_name} from {l_name}.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error removing member: {e}")
                        else:
                            st.info("No other members in this league to remove.")

                with st.expander("👑 3. Conclude Season & Crown Champion", expanded=False):
                    st.caption("Snapshot current mini-league standings, crown the #1 player as Champion, and archive the season into your Hall of Fame.")
                    with st.form(f"conclude_season_form_{l_id}"):
                        season_label_input = st.text_input("Season Label / Title", value="2026 Season", placeholder="e.g., 2026 Office Chumps Season", key=f"input_season_label_{l_id}")
                        confirm_conclude = st.checkbox(f"I confirm I want to conclude the season for {l_name}, archive standings, and crown the winner.", key=f"chk_confirm_conclude_{l_id}")
                        if st.form_submit_button("Crown Champion & Archive Season 🏆", type="primary"):
                            if not confirm_conclude:
                                st.warning("Please check the confirmation box to proceed.")
                            else:
                                try:
                                    league_players_sorted = sorted([p for p in get_cached_profiles() if p["id"] in {m["user_id"] for m in members_res} if members_res], key=lambda x: (-x["tokens"], x["full_name"]))
                                    if league_players_sorted:
                                        champ_prof = supabase.table("profiles").select("unlocked_badges").eq("id", league_players_sorted[0]["id"]).single().execute().data
                                        if champ_prof:
                                            unlocked_b = champ_prof.get("unlocked_badges", []) if isinstance(champ_prof.get("unlocked_badges", []), list) else []
                                            if "🏆 League Champion" not in unlocked_b:
                                                unlocked_b.append("🏆 League Champion")
                                                supabase.table("profiles").update({"unlocked_badges": unlocked_b, "selected_title": "👑 League Champion"}).eq("id", league_players_sorted[0]["id"]).execute()
                                    supabase.table("archived_seasons").insert({"league_id": l_id, "season_label": season_label_input.strip(), "standings_json": league_players_sorted}).execute()
                                    st.cache_data.clear()
                                    st.balloons()
                                    st.success(f"Successfully concluded '{season_label_input}' for {l_name}! Champion crowned and archived to Hall of Fame.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error concluding season: {e}")

                with st.expander("🔑 4. Invite Code & Ownership Tools", expanded=False):
                    col_tc1, col_tc2 = st.columns(2)
                    with col_tc1:
                        st.markdown("##### Regenerate Invite Code")
                        st.caption("Generate a brand new 6-character code, invalidating the old one.")
                        if st.button("Generate New Invite Code 🔑", key=f"btn_regen_{l_id}"):
                            import random as r_m, string as s_m
                            new_code = "".join(r_m.choices(s_m.ascii_uppercase + s_m.digits, k=6))
                            supabase.table("leagues").update({"invite_code": new_code}).eq("id", l_id).execute()
                            st.cache_data.clear()
                            st.success(f"New invite code generated: **{new_code}**")
                            st.rerun()
                    with col_tc2:
                        st.markdown("##### Transfer Ownership")
                        st.caption("Transfer commissioner rights to another member.")
                        other_member_names = {m.get("profiles", {}).get("full_name", "Unknown"): m["user_id"] for m in members_res if m.get("profiles") and m["user_id"] != user_id} if members_res else {}
                        if other_member_names:
                            with st.form(f"transfer_ownership_form_{l_id}"):
                                new_owner_name = st.selectbox("Select New Commissioner", list(other_member_names.keys()), key=f"sel_new_owner_{l_id}")
                                if st.form_submit_button("Transfer Ownership 👑"):
                                    try:
                                        supabase.table("leagues").update({"created_by": other_member_names[new_owner_name]}).eq("id", l_id).execute()
                                        st.cache_data.clear()
                                        st.success(f"Successfully transferred commissioner ownership to {new_owner_name}!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error transferring ownership: {e}")
                        else:
                            st.info("No other members available for transfer.")

    if profile.get("is_admin"):
        with tab_admin:
            st.header("⚙️ System Admin Management Portal")
            admin_sec = st.radio("Select Action", ["Manage Questions", "Auto-Lockout Scheduler", "Grade Week & Calculate Points", "Bulk Token Adjuster", "Export League Data (CSV)", "League Chat Announcement", "Archive & Reset Season", "App Access Control"], horizontal=True)
            
            if admin_sec == "Manage Questions":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #fbbf24; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #fbbf24; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">📋 WEEKLY QUESTIONS & MATCHUPS HUB</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Select a target week to configure matchups, publish prompts, or load quick templates.</p></div>""", unsafe_allow_html=True)
                all_db_weeks = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
                db_week_nums = sorted(list(set([r["week_number"] for r in all_db_weeks]))) if all_db_weeks else []
                next_suggested_week = (db_week_nums[-1] + 1) if db_week_nums else 1
                week_options = db_week_nums + [next_suggested_week] if next_suggested_week not in db_week_nums else db_week_nums

                col_w_sel, col_w_btn1, col_w_btn2 = st.columns([2, 1, 1])
                with col_w_sel:
                    selected_manage_week = st.selectbox("Select Week to Manage", week_options, index=len(week_options) - 1, key="admin_manage_week_sel")
                with col_w_btn1:
                    st.write("")
                    if st.button("📋 Load Templates"):
                        for i in range(1, 11):
                            st.session_state[f"m_prompt_w{selected_manage_week}_q{i}"] = DEFAULT_QUESTION_TEMPLATES[i - 1]
                        st.success("Templates loaded!")
                        st.rerun()
                with col_w_btn2:
                    st.write("")
                    if st.button("🗑️ Clear Week"):
                        try:
                            supabase.table("weekly_questions").delete().eq("week_number", selected_manage_week).eq("winning_answer", "Pending").execute()
                            for i in range(1, 11):
                                if f"m_prompt_w{selected_manage_week}_q{i}" in st.session_state:
                                    del st.session_state[f"m_prompt_w{selected_manage_week}_q{i}"]
                            st.cache_data.clear()
                            st.success(f"Cleared Week {selected_manage_week}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

                real_existing_qs = {q["question_number"]: q for q in get_cached_weekly_questions(selected_manage_week) if q.get("question_number", 0) <= 10}
                st.write("")
                with st.form(key=f"manage_questions_form_week_{selected_manage_week}"):
                    question_payloads = []
                    for i in range(1, 11):
                        st.markdown(f"""<div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.08); border-left: 3px solid #38bdf8; padding: 16px; border-radius: 12px; margin-bottom: 16px;"><span style="font-family: 'Bebas Neue'; font-size: 20px; color: #38bdf8; letter-spacing: 1px;">QUESTION {i} CONFIGURATION</span>""", unsafe_allow_html=True)
                        q_obj = real_existing_qs.get(i, {})
                        raw_txt = q_obj.get("question_text", "")
                        db_prompt = raw_txt.split(" | MATCHUP: ")[0] if " | MATCHUP: " in raw_txt else raw_txt
                        session_key = f"m_prompt_w{selected_manage_week}_q{i}"
                        existing_prompt = st.session_state.get(session_key, db_prompt)
                        existing_away = existing_home = "🏈 Free Agent / Neutral"
                        
                        if " | MATCHUP: " in raw_txt:
                            matchup_part = raw_txt.split(" | MATCHUP: ")[1]
                            if " @ " in matchup_part:
                                split_teams = matchup_part.split(" @ ")
                                existing_away = split_teams[0] if split_teams[0] in NFL_TEAMS else "🏈 Free Agent / Neutral"
                                existing_home = split_teams[1] if split_teams[1] in NFL_TEAMS else "🏈 Free Agent / Neutral"

                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            away_t = st.selectbox(f"Away Team (Q{i})", NFL_TEAMS, index=(NFL_TEAMS.index(existing_away) if existing_away in NFL_TEAMS else 0), key=f"m_away_w{selected_manage_week}_q{i}")
                        with col_m2:
                            home_t = st.selectbox(f"Home Team (Q{i})", NFL_TEAMS, index=(NFL_TEAMS.index(existing_home) if existing_home in NFL_TEAMS else 0), key=f"m_home_w{selected_manage_week}_q{i}")
                        prompt_val = st.text_input(f"Question {i} Prompt", value=existing_prompt, key=session_key, label_visibility="collapsed", placeholder="Enter scenario prompt text...")
                        st.markdown("</div>", unsafe_allow_html=True)
                        question_payloads.append({"question_number": i, "prompt": prompt_val.strip(), "away": away_t, "home": home_t, "db_id": q_obj.get("id")})

                    if st.form_submit_button("Save & Publish All Questions 💾", type="primary"):
                        if any(contains_profanity(item["prompt"]) for item in question_payloads):
                            st.error("⚠️ One or more question prompts contain restricted language. Please check your wording.")
                        else:
                            try:
                                for item in question_payloads:
                                    combined_text = f"{item['prompt']} | MATCHUP: {item['away']} @ {item['home']}"
                                    if item["db_id"]:
                                        supabase.table("weekly_questions").update({"question_text": combined_text}).eq("id", item["db_id"]).execute()
                                    else:
                                        supabase.table("weekly_questions").insert({"week_number": selected_manage_week, "question_number": item["question_number"], "question_text": combined_text, "winning_answer": "Pending"}).execute()
                                st.cache_data.clear()
                                st.success(f"Successfully published all 10 questions for Week {selected_manage_week}!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error publishing questions: {e}")

            elif admin_sec == "Auto-Lockout Scheduler":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #38bdf8; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #38bdf8; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">⏳ KICKOFF LOCKOUT SCHEDULER</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Configure precise kickoff lockout dates and times so picks automatically lock prior to kickoff.</p></div>""", unsafe_allow_html=True)
                all_sched_weeks = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
                sched_week_nums = sorted(list(set([r["week_number"] for r in all_sched_weeks]))) if all_sched_weeks else []
                
                if not sched_week_nums:
                    st.info("No weeks found in the database. Create questions first.")
                else:
                    sel_sched_week = st.selectbox("Select Week for Lockout Scheduler", sched_week_nums, index=len(sched_week_nums) - 1, key="sched_week_select")
                    existing_lock_row = supabase.table("weekly_questions").select("winning_answer").eq("week_number", sel_sched_week).ilike("winning_answer", "LOCKTIME:%").execute().data
                    default_dt = datetime.fromisoformat(existing_lock_row[0]["winning_answer"].replace("LOCKTIME:", "")) if existing_lock_row else datetime.now(timezone.utc)
                    
                    with st.form("lockout_scheduler_form"):
                        col_d, col_t = st.columns(2)
                        with col_d:
                            lock_date = st.date_input("Lockout Date (Sunday Kickoff)", value=default_dt.date())
                        with col_t:
                            lock_time = st.time_input("Lockout Time (UTC)", value=default_dt.time())
                        st.write("")
                        col_btn_set, col_btn_clear = st.columns(2)
                        with col_btn_set:
                            submit_lock = st.form_submit_button("Save Lockout Schedule ⏳", type="primary")
                        with col_btn_clear:
                            clear_lock = st.form_submit_button("Clear Lockout Timer 🗑️", type="secondary")
                        
                        if clear_lock:
                            try:
                                supabase.table("weekly_questions").delete().eq("week_number", sel_sched_week).ilike("winning_answer", "LOCKTIME:%").execute()
                                st.cache_data.clear()
                                st.success(f"Lockout timer cleared for Week {sel_sched_week}!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error clearing lockout: {e}")
                        
                        if submit_lock:
                            iso_str = datetime.combine(lock_date, lock_time).replace(tzinfo=timezone.utc).isoformat()
                            try:
                                supabase.table("weekly_questions").delete().eq("week_number", sel_sched_week).ilike("winning_answer", "LOCKTIME:%").execute()
                                supabase.table("weekly_questions").insert({"week_number": sel_sched_week, "question_number": 99, "question_text": "LOCKTIME SCHEDULER", "winning_answer": f"LOCKTIME:{iso_str}"}).execute()
                                st.cache_data.clear()
                                st.success(f"Successfully scheduled automatic lockout for Week {sel_sched_week} at {iso_str} UTC!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error saving lockout: {e}")

            elif admin_sec == "Grade Week & Calculate Points":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #10b981; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #34d399; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">🏈 LIVE GAME GRADING & TOKEN CALCULATOR</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Update individual match outcomes live as games finish on Sunday. Balances recalculate instantly!</p></div>""", unsafe_allow_html=True)
                all_grading_weeks = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
                grading_week_nums = sorted(list(set([r["week_number"] for r in all_grading_weeks]))) if all_grading_weeks else []
                
                if not grading_week_nums:
                    st.info("No weeks available to grade.")
                else:
                    grade_week_sel = st.selectbox("Select Week to Grade Live", grading_week_nums, index=len(grading_week_nums) - 1, key="grade_week_sel")
                    real_grade_qs = [q for q in get_cached_weekly_questions(grade_week_sel) if q.get("question_number", 0) <= 10 and not q.get("winning_answer", "").startswith("LOCKTIME:")]
                    
                    if not real_grade_qs:
                        st.warning("No questions found for this week to grade.")
                    else:
                        with st.form("live_grading_form"):
                            winning_answers_dict = {}
                            st.markdown("<h4 style='color: #fff; font-family: Bebas Neue; letter-spacing: 1px;'>Live Matchup Results</h4>", unsafe_allow_html=True)
                            for q in real_grade_qs:
                                clean_q_t = q["question_text"].split(" | MATCHUP: ")[0] if " | MATCHUP: " in q["question_text"] else q["question_text"]
                                curr_ans = q.get("winning_answer", "Pending")
                                if curr_ans not in ["Yes", "No"]:
                                    curr_ans = "Pending"
                                
                                st.markdown(f"""<div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255,255,255,0.08); padding: 12px 16px; border-radius: 12px; margin-bottom: 12px;"><b>Question {q["question_number"]}:</b> {clean_q_t}</div>""", unsafe_allow_html=True)
                                winning_answers_dict[q["id"]] = st.selectbox(f"Result for Q{q['question_number']}", ["Pending", "Yes", "No"], index=0 if curr_ans == "Pending" else (1 if curr_ans == "Yes" else 2), key=f"win_ans_{q['id']}", label_visibility="collapsed")
                            
                            st.write("")
                            st.markdown("<h4 style='color: #fff; font-family: Bebas Neue; letter-spacing: 1px;'>Touchdown Scorer Bonus Picks</h4>", unsafe_allow_html=True)
                            week_td_picks = supabase.table("touchdown_picks").select("id, user_id, player_name, is_correct, user_name").eq("week_number", grade_week_sel).execute().data
                            td_grading_dict = {}
                            if week_td_picks:
                                for td in week_td_picks:
                                    td_idx = 1 if td.get("is_correct") is True else (2 if td.get("is_correct") is False else 0)
                                    td_grading_dict[td["id"]] = st.selectbox(f"TD Scorer: {td.get('user_name', 'Player')} picked '{td['player_name']}'", ["Pending", "Correct (+5 🪙)", "Incorrect"], index=td_idx, key=f"td_grade_{td['id']}")
                            else:
                                st.info("No touchdown scorer picks submitted for this week.")
                            
                            st.write("")
                            col_grd1, col_grd2 = st.columns(2)
                            with col_grd1:
                                submit_grading = st.form_submit_button("Save Live Results & Recalculate Tokens 🚀", type="primary")
                            with col_grd2:
                                manual_close_week = st.form_submit_button("Manually Close Week 🔒", type="secondary")
                            
                            if submit_grading:
                                try:
                                    for q_id, chosen_ans in winning_answers_dict.items():
                                        supabase.table("weekly_questions").update({"winning_answer": chosen_ans}).eq("id", q_id).execute()
                                    if week_td_picks:
                                        for td_id, grade_val in td_grading_dict.items():
                                            supabase.table("touchdown_picks").update({"is_correct": True if grade_val == "Correct (+5 🪙)" else (False if grade_val == "Incorrect" else None)}).eq("id", td_id).execute()
                                    recalculate_all_user_balances(supabase)
                                    st.cache_data.clear()
                                    st.success(f"Successfully updated live results for Week {grade_week_sel} and instantly recalculated all player token balances!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error grading week live: {e}")
                            
                            if manual_close_week:
                                try:
                                    supabase.table("weekly_questions").delete().eq("week_number", grade_week_sel).eq("question_number", 96).execute()
                                    supabase.table("weekly_questions").insert({"week_number": grade_week_sel, "question_number": 96, "question_text": "WEEKLY CLOSED MARKER", "winning_answer": "CLOSED"}).execute()
                                    st.cache_data.clear()
                                    st.success(f"Week {grade_week_sel} has been manually closed!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error closing week: {e}")

            elif admin_sec == "Bulk Token Adjuster":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #fbbf24; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #fbbf24; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">💰 BULK TOKEN ADJUSTER</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Quickly adjust token balances for any player across the global league.</p></div>""", unsafe_allow_html=True)
                all_profiles = get_cached_profiles()
                if not all_profiles:
                    st.info("No players found.")
                else:
                    user_map = {p["full_name"]: p for p in all_profiles}
                    with st.form("bulk_token_form"):
                        sel_p_name = st.selectbox("Select Player", list(user_map.keys()))
                        target_p = user_map[sel_p_name]
                        st.markdown(f"""<div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255,255,255,0.08); padding: 14px; border-radius: 12px; margin: 15px 0;">Current Token Balance for <b style="color: #38bdf8;">{sel_p_name}</b>: <span style="font-family: 'Bebas Neue'; font-size: 24px; color: #fbbf24;">{target_p.get("tokens", 10)} 🪙</span></div>""", unsafe_allow_html=True)
                        adjustment_type = st.radio("Adjustment Action", ["Add Tokens (+)", "Subtract Tokens (-)", "Set Absolute Value"], horizontal=True)
                        token_amount_input = st.number_input("Token Amount", min_value=0, max_value=1000, value=5)
                        st.write("")
                        if st.form_submit_button("Apply Token Adjustment 💾", type="primary"):
                            if token_amount_input == 0:
                                st.warning("Please enter a token amount greater than 0.")
                            else:
                                new_tokens = target_p.get("tokens", 10) + token_amount_input if adjustment_type == "Add Tokens (+)" else (max(0, target_p.get("tokens", 10) - token_amount_input) if adjustment_type == "Subtract Tokens (-)" else token_amount_input)
                                try:
                                    supabase.table("profiles").update({"tokens": new_tokens}).eq("id", target_p["id"]).execute()
                                    st.cache_data.clear()
                                    st.success(f"Successfully updated token balance for {sel_p_name} to {new_tokens} 🪙!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error adjusting tokens: {e}")

            elif admin_sec == "Export League Data (CSV)":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #38bdf8; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #38bdf8; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">📊 EXPORT LEAGUE DATA</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Download comprehensive league standings, profiles, and historical bets as CSV reports.</p></div>""", unsafe_allow_html=True)
                all_profiles_export = get_cached_profiles()
                if not all_profiles_export:
                    st.info("No profile data available for export.")
                else:
                    df_export = pd.DataFrame([{"User ID": p["id"], "Full Name": p["full_name"], "Tokens": get_true_global_token_balance(p["id"]), "Favorite Team": p.get("favorite_team", "N/A"), "Selected Title": p.get("selected_title", "N/A")} for p in all_profiles_export])
                    st.download_button(label="📥 Download League Standings CSV", data=df_export.to_csv(index=False).encode("utf-8"), file_name="touchdown_tokens_standings.csv", mime="text/csv", type="primary")

            elif admin_sec == "League Chat Announcement":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #c084fc; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #c084fc; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">📢 COMMISSIONER ANNOUNCEMENT HUB</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Broadcast an official commissioner announcement directly into all league chat feeds.</p></div>""", unsafe_allow_html=True)
                with st.form("admin_announcement_form"):
                    announcement_text = st.text_area("Announcement Message", placeholder="e.g., 🚨 Commissioner Update: Week picks lock in precisely 15 minutes!")
                    target_league_announcement = st.selectbox("Broadcast Target", ["All Leagues & Global Feed", "Global Leaderboard Only"])
                    if st.form_submit_button("Broadcast Announcement 📢", type="primary"):
                        if not announcement_text.strip():
                            st.warning("Announcement message cannot be blank.")
                        elif contains_profanity(announcement_text):
                            st.error("⚠️ Announcement contains restricted language. Please revise.")
                        else:
                            try:
                                supabase.table("trash_talk").insert({"user_id": user_id, "message": f"🚨 **COMMISSIONER ANNOUNCEMENT:** {announcement_text.strip()}", "league_id": "00000000-0000-0000-0000-000000000001"}).execute()
                                st.success("Official commissioner announcement broadcast successfully!")
                            except Exception as e:
                                st.error(f"Error broadcasting announcement: {e}")

            elif admin_sec == "Archive & Reset Season":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #ef4444; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #f87171; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">🏆 GLOBAL SEASON ARCHIVE & RESET</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Archive final global standings, crown the end-of-season Champion, and reset token banks for a fresh season.</p></div>""", unsafe_allow_html=True)
                with st.form("global_season_archive_form"):
                    season_title_input = st.text_input("Global Season Label", value="2026 NFL Season", placeholder="e.g., 2026 NFL Season")
                    confirm_global_reset = st.checkbox("I confirm I want to crown the global champion, archive standings, and reset all player tokens to 10.")
                    if st.form_submit_button("Crown Global Champion & Reset Season 🏆", type="primary"):
                        if not confirm_global_reset:
                            st.warning("Please check the confirmation box to proceed.")
                        else:
                            try:
                                sorted_global_players = sorted(get_cached_profiles(), key=lambda x: (-x["tokens"], x["full_name"]))
                                if sorted_global_players:
                                    champ_profile_res = supabase.table("profiles").select("unlocked_badges").eq("id", sorted_global_players[0]["id"]).single().execute().data
                                    if champ_profile_res:
                                        u_badges = champ_profile_res.get("unlocked_badges", []) if isinstance(champ_profile_res.get("unlocked_badges", []), list) else []
                                        if "🏆 League Champion" not in u_badges:
                                            u_badges.append("🏆 League Champion")
                                            supabase.table("profiles").update({"unlocked_badges": u_badges, "selected_title": "👑 League Champion"}).eq("id", sorted_global_players[0]["id"]).execute()
                                supabase.table("archived_seasons").insert({"league_id": "00000000-0000-0000-0000-000000000001", "season_label": season_title_input.strip(), "standings_json": sorted_global_players}).execute()
                                for p_item in sorted_global_players:
                                    supabase.table("profiles").update({"tokens": 10}).eq("id", p_item["id"]).execute()
                                st.cache_data.clear()
                                st.balloons()
                                st.success(f"Successfully archived '{season_title_input}'! Global Champion crowned and all player token banks reset to 10 tokens.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error archiving global season: {e}")

            elif admin_sec == "App Access Control":
                st.markdown("""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid #38bdf8; padding: 20px; border-radius: 16px; margin-bottom: 25px; backdrop-filter: blur(14px);"><h3 style="color: #38bdf8; font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 1px; margin: 0 0 5px 0;">🔒 GLOBAL APP ACCESS CONTROLS</h3><p style="color: #cbd5e1; font-size: 14px; margin: 0;">Temporarily lock or unlock sign-ins and new account registrations across the entire platform.</p></div>""", unsafe_allow_html=True)
                with st.form("app_access_control_form"):
                    new_signin_lock = st.toggle("Lock All Sign-Ins (Prevent users from logging in)", value=is_signin_locked)
                    new_signup_lock = st.toggle("Lock All New Sign-Ups (Prevent new account registrations)", value=is_signup_locked)
                    if st.form_submit_button("Save Access Control Settings 🔒", type="primary"):
                        supabase.table("weekly_questions").delete().eq("week_number", 998).execute()
                        supabase.table("weekly_questions").insert({"week_number": 998, "question_number": 99, "question_text": "SIGNIN LOCK SETTING", "winning_answer": "LOCKED" if new_signin_lock else "UNLOCKED"}).execute()
                        supabase.table("weekly_questions").delete().eq("week_number", 997).execute()
                        supabase.table("weekly_questions").insert({"week_number": 997, "question_number": 99, "question_text": "SIGNUP LOCK SETTING", "winning_answer": "LOCKED" if new_signup_lock else "UNLOCKED"}).execute()
                        st.cache_data.clear()
                        st.success("App access controls successfully updated!")
                        st.rerun()

st.markdown("""<div style="margin-top: 60px; margin-bottom: 30px; padding: 30px 20px; background: rgba(15, 23, 42, 0.85); border-top: 1px solid rgba(255, 255, 255, 0.12); border-radius: 16px; text-align: center; backdrop-filter: blur(14px); box-shadow: 0 -10px 30px rgba(0,0,0,0.5);"><div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 15px; flex-wrap: wrap;"><a href="https://www.nfl.com" target="_blank" style="color: #94a3b8; font-size: 13px; text-decoration: none;">NFL Official Site</a><span style="color: #475569;">•</span><a href="https://www.espn.com/nfl" target="_blank" style="color: #94a3b8; font-size: 13px; text-decoration: none;">ESPN NFL Scoreboard</a><span style="color: #475569;">•</span><a href="https://buymeacoffee.com/ed.mckenna" target="_blank" style="color: #fbbf24; font-size: 13px; font-weight: bold; text-decoration: none;">☕ Support the App</a></div><p style="color: #64748b; font-size: 12px; line-height: 1.5; max-width: 600px; margin: 0 auto 15px auto;">Touchdown Tokens is an independent, free-to-play recreational sports prediction platform built for community entertainment. All virtual tokens hold zero cash value. Not affiliated with or endorsed by the National Football League (NFL).</p><div style="color: #94a3b8; font-size: 12px; font-weight: 600;">&copy; 2026 Touchdown Tokens. All rights reserved. Designed & Engineered by Ed McKenna.</div><div style="margin-top: 20px;"><a href="https://buymeacoffee.com/ed.mckenna" target="_blank" style="display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 10px 22px; border-radius: 12px; font-family: 'Teko', sans-serif; font-size: 20px; letter-spacing: 1px; font-weight: bold; text-decoration: none; box-shadow: 0 4px 15px rgba(251, 191, 36, 0.3);">☕ Buy Me A Coffee</a></div></div>""", unsafe_allow_html=True)
