from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_token, current_user, hash_password, verify_password
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


def _out(u: User) -> dict:
    return {"token": create_token(u), "user": {"id": u.id, "name": u.name, "email": u.email}}


@router.post("/signup")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    u = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    return _out(u)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return _out(u)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}
