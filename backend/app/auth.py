import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from pymongo import MongoClient
from dotenv import load_dotenv
from bson.objectid import ObjectId
from app.jwt import create_access_token

load_dotenv()

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["nudge_db"]
users = db["users"]

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI router
router = APIRouter(prefix="/auth", tags=["Auth"])

# User creation model
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Login model
class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup")
def signup(user: UserCreate):
    if users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered.")
    
    hashed_password = pwd_context.hash(user.password)
    result = users.insert_one({"email": user.email, "hashed_password": hashed_password})
    if result.inserted_id:
        return {"message": "Account created successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to create user")

@router.post("/login")
def login(user: UserLogin):
    db_user = users.find_one({"email": user.email})
    if not db_user or not pwd_context.verify(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    
    token = create_access_token(data={"sub": str(db_user["_id"])})
    return {"access_token": token, "token_type": "bearer"}

# Optional route for debugging
@router.get("/me/{email}")
def check_user(email: str):
    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": user["email"], "id": str(user["_id"])}
