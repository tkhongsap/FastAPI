from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime
import bcrypt
import secrets
from urllib.parse import quote
from email_utils import send_email  # Import the send_email function

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# MongoDB setup
mongo_uri = os.environ['MONGO_AUTH']
client = MongoClient(mongo_uri)
db = client['IntelligenceHub']
users_collection = db['users']

# Ensure indexes are created
users_collection.create_index("email", unique=True)

class UserRegistration(BaseModel):
    email: EmailStr
    name: str
    password: str

class EmailSchema(BaseModel):
    email: EmailStr

@app.post("/register")
async def register_user(user: UserRegistration):
    existing_user = users_collection.find_one({'email': user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
    user_data = {
        "email": user.email,
        "name": user.name,
        "password": hashed_password,
        "verified": False,
        "created": datetime.utcnow()
    }
    
    try:
        users_collection.insert_one(user_data)
        return {"message": "User registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registering user: {e}")

@app.post("/send_verification")
async def send_verification(email_schema: EmailSchema):
    email = email_schema.email
    token = secrets.token_hex(20)
    existing_user = users_collection.find_one({'email': email})

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
            "email": email,
            "token": token,
            "verified": False
        })

    verification_url = os.getenv("EMAIL_BASE_URL")
    msg = f'<p>Welcome to IntelligenceHub.ai!</p><p>Please click on the following link to verify your email:</p><a href="{verification_url}/verify?token={token}&email={quote(email)}">Verify Email</a><p>Thank you,</p><p>IntelligenceHub.ai Team</p>'
    subject = 'Email verification'
    send_email(subject, msg, email)

    return {"message": "Verification email sent"}

@app.get("/verify")
async def verify_email(token: str, email: str):
    user = users_collection.find_one({'email': email, 'token': token})

    if user:
        if user.get('verified', False):
            return "Email is already verified."
        
        users_collection.update_one(
            {'_id': user['_id']},
            {"$set": {'verified': True}}
        )
        return "Email has been successfully verified."

    raise HTTPException(status_code=400, detail="Invalid token or email")

# Close MongoDB client connection when FastAPI shuts down
@app.on_event("shutdown")
def shutdown_event():
    client.close()

