import os
import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "")

def send_weekly_reminders(supabase_client, week_number: int) -> int:
    """Sends pick submission reminders to users with email_notifications enabled."""
    success_count = 0
    try:
        profiles_res = supabase_client.table("profiles").select("email, full_name").eq("email_notifications", True).execute()
        users_to_notify = profiles_res.data if profiles_res.data else []

        for p in users_to_notify:
            email = p.get("email")
            name = p.get("full_name", "Fan")
            if not email:
                continue

            html_content = f"""
            <div style="background-color: #0f172a; padding: 30px; color: #fff; font-family: sans-serif; border-radius: 12px; border-top: 4px solid #fbbf24;">
                <h2 style="color: #fbbf24; margin-top: 0;">Hey {name}, Week {week_number} Picks Are Due Soon! ⏳</h2>
                <p style="color: #cbd5e1; line-height: 1.5;">Don't forget to lock in your weekly match predictions and assign your token wagers before the official lockout deadline.</p>
                <a href="https://tdtokens.co.uk/bets?week={week_number}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 8px; display: inline-block; margin-top: 15px; box-shadow: 0 4px 15px rgba(251,191,36,0.3);">Submit Your Picks 🏈</a>
            </div>
            """
            try:
                resend.Emails.send({
                    "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
                    "to": [email],
                    "subject": f"🏈 Reminder: Submit Your Week {week_number} Picks!",
                    "html": html_content
                })
                success_count += 1
            except Exception as email_err:
                print(f"Failed to send pick reminder to {email}: {email_err}")

        return success_count
    except Exception as e:
        print(f"Error bulk sending pick reminders: {e}")
        return success_count

def send_grading_notifications(supabase_client, week_number: int) -> int:
    """Sends graded results notifications to users with grading_emails enabled."""
    success_count = 0
    try:
        profiles_res = supabase_client.table("profiles").select("email, full_name").eq("grading_emails", True).execute()
        users_to_notify = profiles_res.data if profiles_res.data else []

        for p in users_to_notify:
            email = p.get("email")
            name = p.get("full_name", "Fan")
            if not email:
                continue

            html_content = f"""
            <div style="background-color: #0f172a; padding: 30px; color: #fff; font-family: sans-serif; border-radius: 12px; border-top: 4px solid #10b981;">
                <h2 style="color: #34d399; margin-top: 0;">Week {week_number} Has Been Graded! 📊</h2>
                <p style="color: #cbd5e1; line-height: 1.5;">Hey {name}, official game results and token payouts for Week {week_number} have just been processed. Log in to check your updated balance and standings!</p>
                <a href="https://tdtokens.co.uk/dashboard" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #fff; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 8px; display: inline-block; margin-top: 15px; box-shadow: 0 4px 15px rgba(16,185,129,0.3);">View Results & Standings 🏆</a>
            </div>
            """
            try:
                resend.Emails.send({
                    "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
                    "to": [email],
                    "subject": f"📊 Results In: Week {week_number} Grades & Token Payouts!",
                    "html": html_content
                })
                success_count += 1
            except Exception as email_err:
                print(f"Failed to send grading email to {email}: {email_err}")

        return success_count
    except Exception as e:
        print(f"Error bulk sending grading notifications: {e}")
        return success_count
