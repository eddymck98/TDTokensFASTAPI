import os
import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "")

def send_weekly_reminders_to_all(supabase_client, week_number: int) -> int:
    """Fetches all users with email_notifications enabled and sends them a weekly reminder."""
    success_count = 0
    try:
        # Fetch profiles where notifications are explicitly enabled
        profiles_res = supabase_client.table("profiles").select("email, full_name").eq("email_notifications", True).execute()
        users_to_notify = profiles_res.data if profiles_res.data else []

        for p in users_to_notify:
            email = p.get("email")
            name = p.get("full_name", "Fan")
            if not email:
                continue

            html_content = f"""
            <div style="background-color: #0f172a; padding: 30px; color: #fff; font-family: sans-serif; border-radius: 12px; border-top: 4px solid #fbbf24;">
                <h2 style="color: #fbbf24; margin-top: 0;">Hey {name}, Week {week_number} is locking soon! ⏳</h2>
                <p style="color: #cbd5e1; line-height: 1.5;">Don't forget to lock in your predictions and assign your token wagers before the official weekly deadline.</p>
                <a href="https://tdtokens.co.uk/bets?week={week_number}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 8px; display: inline-block; margin-top: 15px; box-shadow: 0 4px 15px rgba(251,191,36,0.3);">Make Your Picks 🏈</a>
            </div>
            """
            try:
                resend.Emails.send({
                    "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
                    "to": [email],
                    "subject": f"🏈 Reminder: Week {week_number} Picks Due Soon!",
                    "html": html_content
                })
                success_count += 1
            except Exception as email_err:
                print(f"Failed to send to {email}: {email_err}")

        return success_count
    except Exception as e:
        print(f"Error bulk sending reminders: {e}")
        return success_count
