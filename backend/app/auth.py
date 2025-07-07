import os
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from pymongo import MongoClient
from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer

# Load environment variables
load_dotenv()

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("JWT_SECRET", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["nudge_db"]
users = db["users"]

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI router
router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# ─────────────────────────────────────────────────────────────
# Token Utilities
# ─────────────────────────────────────────────────────────────
def create_access_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

# ✅ DEV MODE: Always return "ram_nathawat"
def verify_token(authorization: str = Header(default="Bearer test")) -> str:
    return "ram_nathawat"

# ─────────────────────────────────────────────────────────────
# Auth Routes
# ─────────────────────────────────────────────────────────────

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

@router.get("/me/{email}")
def check_user(email: str):
    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": user["email"], "id": str(user["_id"])}
