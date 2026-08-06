import os
from supabase import Client

def sync_and_get_user_badges(supabase: Client, target_user_id: str, check_celebration: bool = False, st_session_state=None) -> list:
    """
    Syncs and calculates all unlocked Master Badges for a target user based on their historical bets,
    touchdown picks, tokens, mini-league memberships, and leaderboard performance.
    """
    try:
        p_data = supabase.table("profiles").select("tokens, unlocked_badges").eq("id", target_user_id).single().execute().data
        if not p_data:
            return []
    except Exception:
        return []

    toks = p_data.get("tokens", 10)
    existing_unlocked = p_data.get("unlocked_badges") if isinstance(p_data.get("unlocked_badges"), list) else []
    
    u_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", target_user_id).execute().data
    u_td = supabase.table("touchdown_picks").select("*").eq("user_id", target_user_id).eq("is_correct", True).order("week_number").execute().data

    newly_earned = set(existing_unlocked)
    
    # Check if user is a league commissioner or admin
    is_commish = bool(supabase.table("leagues").select("id").eq("created_by", target_user_id).execute().data)
    is_adm = bool(supabase.table("profiles").select("is_admin").eq("id", target_user_id).single().execute().data.get("is_admin", False))
    if is_commish or is_adm:
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
    joined_l_ids = [m["league_id"] for m in my_joined_leagues] if my_joined_leagues else []
    if len(joined_l_ids) >= 3:
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
        w_num, w_ans = b["week_number"], b.get("weekly_questions", {}).get("winning_answer")
        weeks_played.add(w_num)
        if w_num not in weekly_nets:
            weekly_nets[w_num] = {"gains": 0, "losses": 0, "large_wager_hits": 0}
        if w_ans in ["Yes", "No"]:
            if b["pick"] == w_ans:
                total_lifetime_won += b["wager_amount"]
                weekly_nets[w_num]["gains"] += b["wager_amount"]
                if b["wager_amount"] >= 5:
                    weekly_nets[w_num]["large_wager_hits"] += 1
            else:
                weekly_nets[w_num]["losses"] += b["wager_amount"]

    for td in u_td:
        if td["week_number"] in weekly_nets:
            weekly_nets[td["week_number"]]["gains"] += 5

    if total_lifetime_won >= 50:
        newly_earned.add("🚀 Token Tycoon")

    sorted_weeks, consecutive_oracle_weeks = sorted(list(weekly_nets.keys())), 0
    for w in sorted_weeks:
        week_bets_list = [b for b in u_bets if b["week_number"] == w]
        if any(b["wager_amount"] >= 5 and b["pick"] == b.get("weekly_questions", {}).get("winning_answer") for b in week_bets_list):
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

    # Evaluate Mini-League specific badges
    for l_id in joined_l_ids:
        if l_id == "00000000-0000-0000-0000-000000000001":
            continue
        league_members_res = supabase.table("league_members").select("user_id").eq("league_id", l_id).execute().data
        peer_ids = [m["user_id"] for m in league_members_res] if league_members_res else []
        if peer_ids:
            # Calculate mini-league leaderboard stats
            mini_stats = []
            leader_res = supabase.table("profiles").select("id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title, featured_badges, unlocked_badges, favorite_player, bio, default_league_view, email_notifications, high_contrast_mode, reduced_motion").execute().data
            if leader_res:
                for p in leader_res:
                    if p["id"] not in peer_ids:
                        continue
                    p_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", p["id"]).execute().data
                    p_wins, p_graded = 0, 0
                    for pb in p_bets:
                        p_w_ans = pb.get("weekly_questions", {}).get("winning_answer")
                        if p_w_ans in ["Yes", "No"]:
                            p_graded += 1
                            if pb["pick"] == p_w_ans:
                                p_wins += 1
                    mini_stats.append({
                        **p,
                        "tokens": p.get("tokens", 10),
                        "win_rate": int((p_wins / p_graded) * 100) if p_graded > 0 else 0,
                        "total_bets": p_graded
                    })
                mini_stats = sorted(mini_stats, key=lambda x: (-x["tokens"], x["full_name"]))
                
                if mini_stats and mini_stats[0]["id"] == target_user_id:
                    newly_earned.add("🛡️ Mini-League Monarch")
                
                my_mini_stat = next((s for s in mini_stats if s["id"] == target_user_id), None)
                if my_mini_stat and my_mini_stat["win_rate"] >= 70 and my_mini_stat["total_bets"] >= 20:
                    newly_earned.add("🌟 Gridiron General")

    # Evaluate weekly high scorer and perfect 10/10
    graded_q = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).neq("winning_answer", "Pending").neq("winning_answer", "LOCKED").order("week_number", desc=True).execute().data
    if graded_q:
        latest_w = graded_q[0]["week_number"]
        all_latest_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("week_number", latest_w).execute().data
        user_gains, user_loss, user_correct = {}, {}, {}
        for b in all_latest_bets:
            u, w_ans = b["user_id"], b.get("weekly_questions", {}).get("winning_answer")
            if u not in user_gains:
                user_gains[u], user_loss[u], user_correct[u] = 0, 0, 0
            if w_ans in ["Yes", "No"]:
                if b["pick"] == w_ans:
                    user_gains[u] += b["wager_amount"]
                    user_correct[u] += 1
                else:
                    user_loss[u] += b["wager_amount"]
        if user_gains and max(user_gains.values(), default=-1) > 0 and max(user_gains, key=user_gains.get) == target_user_id:
            newly_earned.add("👑 Weekly High Scorer")
        if user_loss and max(user_loss.values(), default=-1) > 0 and max(user_loss, key=user_loss.get) == target_user_id:
            newly_earned.add("📉 Wall Street Bets")
        if user_correct.get(target_user_id, 0) == 10:
            newly_earned.add("🎯 Perfect 10/10")

    final_badges_list = list(newly_earned)
    if set(final_badges_list) != set(existing_unlocked):
        try:
            supabase.table("profiles").update({"unlocked_badges": final_badges_list}).eq("id", target_user_id).execute()
        except Exception:
            pass

    if check_celebration and st_session_state is not None:
        cache_key = f"seen_badges_{target_user_id}"
        if cache_key not in st_session_state:
            st_session_state[cache_key] = final_badges_list
        else:
            newly_detected = [b for b in final_badges_list if b not in st_session_state[cache_key]]
            if newly_detected:
                st_session_state[cache_key] = final_badges_list
                return {"badges": final_badges_list, "newly_detected": newly_detected}

    return final_badges_list
