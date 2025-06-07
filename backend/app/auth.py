import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from pymongo import MongoClient
from dotenv import load_dotenv
from bson.objectid import ObjectId
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer

# Load environment variables
load_dotenv()

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("JWT_SECRET", "supersecret")  # Changed to JWT_SECRET to match .env
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

# User creation model
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Login model
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# ✅ Create JWT token
def create_access_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

# ✅ Token verification
def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Token verification failed")

# ✅ Signup Route
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

# ✅ Login Route
@router.post("/login")
def login(user: UserLogin):
    db_user = users.find_one({"email": user.email})
    if not db_user or not pwd_context.verify(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    
    token = create_access_token(data={"sub": str(db_user["_id"])})
    return {"access_token": token, "token_type": "bearer"}

# ✅ Optional: Check if user exists (debug)
@router.get("/me/{email}")
def check_user(email: str):
    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": user["email"], "id": str(user["_id"])}

