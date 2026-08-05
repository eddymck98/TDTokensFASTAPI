import os
import resend

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

def send_verification_email(to_email: str, verification_link: str) -> bool:
    """Sends account confirmation email via Resend API."""
    try:
        html_content = f"""
        <div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" style="width: 180px; margin-bottom: 15px;" />
                    <h1 style="color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1>
                    <p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Weekly NFL Predictions & Wagers</p>
                </div>
                <h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3>
                <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">Thanks for registering an account with Touchdown Tokens. To lock in your weekly picks, compete on leaderboards, and claim your tokens, please authorize your email address below:</p>
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{verification_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; display: inline-block;">AUTHORISE EMAIL ADDRESS</a>
                </div>
            </div>
        </div>
        """
        resend.Emails.send({
            "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
            "to": [to_email],
            "subject": "🏈 Authorise Your Touchdown Tokens Account",
            "html": html_content
        })
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
