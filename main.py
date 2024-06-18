"""
This FastAPI application serves as a backend for managing user leads and verifying email addresses.

Main Functionalities:
1. User and Lead Management:
   - Leads: Individuals who have shown interest in a product or service.
   - Users: Registered users of the system.

2. Email Verification:
   - When a user or lead signs up, an email verification link is sent to their email address.
   - This helps ensure that the email address provided is valid and that the user/lead is legitimate.

3. Endpoints:
   - Create Lead (/create_lead):
       - Accepts information about a lead (name, email, phone).
       - Stores this information in a MongoDB database.
       - Sends a verification email to the lead.
   - Send Verification (/send_verification):
       - Accepts an email address to verify.
       - Checks if the email is already verified.
       - If not, sends a verification email.
   - Verify Client (/verify_client):
       - Takes a token, email, and optionally a phone number and database type.
       - Verifies the token and email combination in the database.
       - If valid, marks the email as verified and allows the user/lead to log in.

4. MongoDB:
   - The application uses MongoDB to store user and lead data.
   - It connects to MongoDB using credentials stored in environment variables.

5. Email Sending:
   - Uses the smtplib library to send emails.
   - The email credentials are securely loaded from environment variables.

6. Environment Variables:
   - Sensitive information like database URIs and email passwords are stored in environment variables for security.
"""


from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

app = FastAPI()

# MongoDB setup
mongo_uri = os.environ['MONGO_AUTH']
client = MongoClient(mongo_uri)
db = client['IntelligenceHub']
users_collection = db['users']
leads_collection = db['leads']

email_base_url = os.environ['EMAIL_BASE_URL']

class EmailSchema(BaseModel):
    email: EmailStr
    id: Optional[str]

class LeadSchema(BaseModel):
    name: str
    email: EmailStr
    phone: str
    id: Optional[str]

def send_email(subject, message, to_address):
    from_address = 'ta.khongsap@live.com'
    password = os.getenv("EMAIL_PASS")
    if not password:
        raise ValueError("The EMAIL_PASS environment variable is not set")

    msg = MIMEMultipart()
    msg['From'] = "IntelligenceAgent.ai - Email verification <" + from_address + ">"
    msg['To'] = to_address
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'html'))
    server = smtplib.SMTP('smtp.office365.com', 587)
    server.starttls()
    server.login(from_address, password)
    text = msg.as_string()
    server.sendmail(from_address, to_address, text)
    server.quit()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <h1>Welcome to IntelligenceHub API</h1>
    <p>Use the available endpoints to interact with the system.</p>
    <ul>
        <li><a href="/docs">API Documentation</a></li>
    </ul>
    """

@app.post("/create_lead")
async def create_lead(lead: LeadSchema):
    token = secrets.token_hex(20)
    existing_lead = leads_collection.find_one({'email': lead.email})

    if existing_lead:
        if existing_lead.get('verified', False):
            return {"message": "Email is already verified"}

        leads_collection.update_one(
            {'_id': existing_lead['_id']},
            {
                "$set": {
                    "name": lead.name,
                    "phone": lead.phone,
                    "token": token,
                    "verified": False
                }
            }
        )
    else:
        leads_collection.insert_one({
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "token": token,
            "verified": False
        })

    msg = f'<p>Welcome to IntelligenceHub.ai, {lead.name}!</p><p>Please click on the following link to verify your email:</p><a href="{email_base_url}/verify_client?token={token}&email={quote(lead.email)}&phone={quote(lead.phone)}&db_type=leads">Verify Email</a><p>Thank you,</p><p>IntelligenceHub.ai Team</p>'
    subject = 'Email verification'
    send_email(subject, msg, lead.email)

    return {"message": "Verification email sent"}

@app.post("/send_verification")
async def send_verification(email: EmailSchema):
    token = secrets.token_hex(20)
    existing_user = users_collection.find_one({'email': email.email})

    if existing_user:
        if existing_user.get('verified', False):
            return {"message": "Email is already verified"}

        users_collection.update_one(
            {'_id': existing_user['_id']},
            {
                "$set": {
                    "token": token,
                    "verified": False
                }
            }
        )
    else:
        users_collection.insert_one({
            "email": email.email,
            "token": token,
            "verified": False
        })

    msg = f'<p>Welcome to IntelligenceHub.ai!</p><p>Please click on the following link to verify your email:</p><a href="{email_base_url}/verify_client?token={token}&email={quote(email.email)}&db_type=users">Verify Email</a><p>Thank you,</p><p>IntelligenceHub.ai Team</p>'
    subject = 'Email verification'
    send_email(subject, msg, email.email)

    return {"message": "Verification email sent"}

@app.get("/verify_client", response_class=HTMLResponse)
async def verify_client(token: str, email: str, phone: Optional[str] = None, db_type: str = "users"):
    collection = users_collection if db_type == "users" else leads_collection
    record = collection.find_one({'email': email, 'token': token})

    if record:
        if record.get('verified', False):
            return """
            <h1>This email has already been verified!</h1>
            <p>You are fully verified and can now login.</p>
            <a href="https://saas-production-7cf3.up.railway.app/">Click here to login</a>
            """
        else:
            collection.update_one(
                {'_id': record['_id']},
                {"$set": {'verified': True}}
            )
            return """
            <h1>Your email has been successfully verified!</h1>
            <p>You are fully verified and can now login.</p>
            <a href="https://saas-production-7cf3.up.railway.app/">Click here to login</a>
            """

    raise HTTPException(status_code=400, detail="Invalid token or email")

# Close MongoDB client connection when FastAPI shuts down
@app.on_event("shutdown")
def shutdown_event():
    client.close()
