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
        # Send the email using Resend to AK4MVP@gmail.com
        params = {
            "from": "Platform Support <onboarding@resend.dev>",  # Change this if you have a verified domain on Resend
            "to": ["AK4MVP@gmail.com"],
            "subject": f"New Contact Form Submission from {sender_email}",
            "html": f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                    <h2 style="color: #d97706;">New Contact Message Received</h2>
                    <p><strong>From / Contact Info:</strong> {sender_email}</p>
                    <p><strong>Message:</strong></p>
                    <blockquote style="background: #f9fafb; border-left: 4px solid #d97706; padding: 12px; margin: 0;">
                        {message_body}
                    </blockquote>
                </div>
            """,
        }
        
        resend.Emails.send(params)
        
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
            context={"request": request, "success": False}
        )
