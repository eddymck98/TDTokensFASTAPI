import os
import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "")

# Shared HTML header containing the brand logo banner
LOGO_BANNER = """
<div style="text-align: center; margin-bottom: 25px;">
    <div style="display: inline-block; background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); border: 2px solid #fbbf24; padding: 12px 24px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
        <span style="font-family: 'Bebas Neue', Arial, sans-serif; font-size: 26px; color: #fbbf24; letter-spacing: 2px;">🏈 TOUCHDOWN TOKENS</span>
    </div>
</div>
"""

def send_weekly_reminders(supabase_client, week_number: int) -> int:
    """Sends professional pick submission reminders to users with email_notifications enabled."""
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
            <div style="background-color: #0b0f19; padding: 40px 20px; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #0f172a; border: 1px solid rgba(255,255,255,0.1); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 35px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                    
                    {LOGO_BANNER}
                    
                    <h2 style="color: #fbbf24; font-family: 'Bebas Neue', Arial, sans-serif; font-size: 28px; letter-spacing: 1px; margin-top: 0; text-align: center;">WEEK {week_number} PICKS ARE DUE SOON! ⏳</h2>
                    
                    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 20px;">
                        Hey <strong>{name}</strong>,
                    </p>
                    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">
                        The clock is ticking down to kickoff! Make sure you lock in your weekly matchup predictions and position your token wagers before the official lockout deadline.
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://tdtokens.co.uk/bets?week={week_number}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; font-family: 'Teko', Arial, sans-serif; font-size: 20px; font-weight: bold; letter-spacing: 1px; border-radius: 10px; display: inline-block; box-shadow: 0 4px 15px rgba(251,191,36,0.4);">SUBMIT YOUR PICKS 🏈</a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 30px 0;">
                    
                    <p style="color: #64748b; font-size: 12px; text-align: center; margin: 0;">
                        You are receiving this email because you opted into weekly pick notifications on <a href="https://tdtokens.co.uk" style="color: #38bdf8; text-decoration: none;">Touchdown Tokens</a>.<br>
                        You can update your email preferences anytime from your <a href="https://tdtokens.co.uk/profile" style="color: #38bdf8; text-decoration: none;">Profile Settings</a>.
                    </p>
                </div>
            </div>
            """
            try:
                resend.Emails.send({
                    "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
                    "to": [email],
                    "subject": f"🏈 Reminder: Submit Your Week {week_number} Picks Before Kickoff!",
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
    """Sends professional graded results announcements to users with grading_emails enabled."""
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
            <div style="background-color: #0b0f19; padding: 40px 20px; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #0f172a; border: 1px solid rgba(255,255,255,0.1); border-top: 4px solid #10b981; border-radius: 16px; padding: 35px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                    
                    {LOGO_BANNER}
                    
                    <h2 style="color: #34d399; font-family: 'Bebas Neue', Arial, sans-serif; font-size: 28px; letter-spacing: 1px; margin-top: 0; text-align: center;">WEEK {week_number} HAS BEEN GRADED! 📊</h2>
                    
                    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 20px;">
                        Hey <strong>{name}</strong>,
                    </p>
                    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">
                        Official matchup results, player stats, and token payouts for <strong>Week {week_number}</strong> have just been finalized and processed. Log in now to check your updated token balance and league standings!
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://tdtokens.co.uk/dashboard" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #ffffff; padding: 14px 28px; text-decoration: none; font-family: 'Teko', Arial, sans-serif; font-size: 20px; font-weight: bold; letter-spacing: 1px; border-radius: 10px; display: inline-block; box-shadow: 0 4px 15px rgba(16,185,129,0.4);">VIEW RESULTS & STANDINGS 🏆</a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 30px 0;">
                    
                    <p style="color: #64748b; font-size: 12px; text-align: center; margin: 0;">
                        You are receiving this email because you opted into grading update notifications on <a href="https://tdtokens.co.uk" style="color: #38bdf8; text-decoration: none;">Touchdown Tokens</a>.<br>
                        You can update your email preferences anytime from your <a href="https://tdtokens.co.uk/profile" style="color: #38bdf8; text-decoration: none;">Profile Settings</a>.
                    </p>
                </div>
            </div>
            """
            try:
                resend.Emails.send({
                    "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
                    "to": [email],
                    "subject": f"📊 Results In: Week {week_number} Grades & Token Payouts Announced!",
                    "html": html_content
                })
                success_count += 1
            except Exception as email_err:
                print(f"Failed to send grading email to {email}: {email_err}")

        return success_count
    except Exception as e:
        print(f"Error bulk sending grading notifications: {e}")
        return success_count
