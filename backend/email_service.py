import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

def send_otp_email(to_email: str, otp_code: str) -> bool:
    """
    Sends an OTP code via email using SMTP.
    Returns True if successful, False otherwise.
    """
    # Force reload of .env so hot-reloads pick up new credentials
    load_dotenv(override=True)
    
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")

    if not SMTP_USER or not SMTP_PASS:
        print(f"WARNING: SMTP credentials not set. Simulated email to {to_email}: {otp_code}")
        return False

    msg = EmailMessage()
    msg['Subject'] = 'Your ExpenseOps Verification Code'
    msg['From'] = SMTP_USER
    msg['To'] = to_email

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; padding: 20px;">
        <h2 style="color: #0d9488;">ExpenseOps Verification</h2>
        <p>Hello,</p>
        <p>Your one-time verification code is:</p>
        <h1 style="font-size: 32px; letter-spacing: 4px; color: #111827; background-color: #f3f4f6; padding: 10px; border-radius: 6px; display: inline-block;">
          {otp_code}
        </h1>
        <p>This code will expire in 10 minutes.</p>
        <p>If you did not request this, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin-top: 30px;">
        <p style="font-size: 12px; color: #6b7280;">ExpenseOps System</p>
      </body>
    </html>
    """
    
    msg.set_content("Your ExpenseOps Verification Code is: " + otp_code)
    msg.add_alternative(html_content, subtype='html')

    try:
        # Connect securely and send
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False
