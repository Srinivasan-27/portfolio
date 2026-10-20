# 1. Import necessary libraries
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from typing import List
import os
from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

# 2. Load environment variables
load_dotenv()

# 3. Create a FastAPI app instance
app = FastAPI(
    title="Portfolio Contact API",
    description="A simple API to handle a portfolio contact form and send emails.",
    version="2.0.0"
)

# 4. Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 5. Pydantic Model for request body validation
class ContactForm(BaseModel):
    fullname: str
    email: EmailStr
    message: str

# 6. FastAPI-Mail Configuration
conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_FROM"),
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER = os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", 'True').lower() in ('true', '1', 't'),
    MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", 'False').lower() in ('true', '1', 't'),
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

# 7. Define API Routes
@app.get("/")
async def read_root(request: Request):
    """
    Serves the main HTML page.
    """
    return templates.TemplateResponse(
    request=request,
    name="index.html"
)

@app.post("/api/contact", status_code=status.HTTP_200_OK)
async def submit_contact_form(contact: ContactForm):
    """
    Receives contact form data, validates it, and sends it as an email.
    """
    html = f"""
    <h3>New Contact Form Submission</h3>
    <p><b>Name:</b> {contact.fullname}</p>
    <p><b>Email:</b> {contact.email}</p>
    <p><b>Message:</b></p>
    <p>{contact.message}</p>
    """

    message = MessageSchema(
        subject=f"New Portfolio Contact: {contact.fullname}",
        recipients=[os.getenv("MAIL_FROM")],  # Sends the email to yourself
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        return {"status": "success", "message": "Contact form submitted successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email. Error: {str(e)}"
        )

# 8. Run the application (for development)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
