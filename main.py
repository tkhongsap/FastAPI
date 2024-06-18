import os
import logging
import secrets

from urllib.parse import quote
from fastapi.responses import HTMLResponse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from dotenv import load_dotenv
from pymongo import MongoClient
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pprint import pprint

# Set up basic configuration for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

app = FastAPI()

# MongoDB setup
mongo_uri = os.environ['MONGO_AUTH']
client = MongoClient(mongo_uri)
db = client['IntelligenceHub']
users_collection = db['users']
leads_collection = db['leads']

email_base_url = os.environ['EMAIL_BASE_URL']
brevo_api_key = os.getenv("BREVO_API_KEY")

class EmailSchema(BaseModel):
    email: EmailStr
    id: Optional[str] = None

class LeadSchema(BaseModel):
    name: str
    email: EmailStr
    phone: str
    id: Optional[str]

def send_email(subject, message, to_address):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = brevo_api_key

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    sender = {"name": "IntelligenceHub.ai", "email": "tkhongsap@ka-analytics.com"}
    to = [{"email": to_address}]
    html_content = f"<html><body><p>{message}</p></body></html>"

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        sender=sender,
        subject=subject,
        html_content=html_content
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        pprint(api_response)
    except ApiException as e:
        logging.error(f"Exception when calling SMTPApi->send_transac_email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")

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

