import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def send_email(subject, message, to_address):
    from_address = 'ta.khongsap@live.com'
    password = os.getenv("EMAIL_PASS")
    if not password:
        raise ValueError("The EMAIL_PASS environment variable is not set")

    msg = MIMEMultipart()
    msg['From'] = f"IntelligenceAgent.ai - Email verification <{from_address}>"
    msg['To'] = to_address
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'html'))
    try:
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(from_address, password)
        text = msg.as_string()
        server.sendmail(from_address, to_address, text)
        server.quit()
        print(f"Email sent to {to_address}")
    except Exception as e:
        print(f"Failed to send email to {to_address}: {e}")
        raise

