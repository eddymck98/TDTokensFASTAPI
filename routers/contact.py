import os
import resend
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Initialize Resend with your API key from environment variables
resend.api_key = os.getenv("RESEND_API_KEY")

@router.get("/contact", response_class=HTMLResponse)
async def contact_get(request: Request, success: bool = False):
    return templates.TemplateResponse(
        request,
        name="contact.html",
        context={"request": request, "success": success}
    )

@router.post("/contact", response_class=HTMLResponse)
async def contact_post(
    request: Request,
    sender_email: str = Form(...),
    message_body: str = Form(...)
):
    try:
        # Check if API key is loaded properly
        if not resend.api_key:
            print("Resend Error: RESEND_API_KEY environment variable is missing.")
            raise Exception("API key not configured")

        # Send the email using Resend to eddymck98@gmail.com
        # Note: If using Resend's test domain 'onboarding@resend.dev', 
        # ensure your Resend account email matches or use a verified domain.
        params = {
            "from": "Touchdown Tokens Support <onboarding@resend.dev>",
            "to": ["eddymck98@gmail.com"],
            "subject": f"New Contact Form Submission from {sender_email}",
            "html": f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; background: #f4f4f5; border-radius: 8px;">
                    <h2 style="color: #d97706; margin-top: 0;">New Contact Message Received</h2>
                    <p><strong>From / Contact Info:</strong> {sender_email}</p>
                    <p><strong>Message:</strong></p>
                    <div style="background: #ffffff; border-left: 4px solid #d97706; padding: 15px; border-radius: 4px; margin-top: 5px;">
                        {message_body}
                    </div>
                </div>
            """,
        }
        
        response = resend.Emails.send(params)
        print(f"Resend Success Response: {response}")
        
        # Redirect back to /contact with success=True flag to trigger the success banner prompt
        return templates.TemplateResponse(
            request,
            name="contact.html",
            context={"request": request, "success": True}
        )
        
    except Exception as e:
        print(f"Error sending contact email via Resend: {e}")
        return templates.TemplateResponse(
            request,
            name="contact.html",
            context={"request": request, "success": False, "error_message": str(e)}
        )
