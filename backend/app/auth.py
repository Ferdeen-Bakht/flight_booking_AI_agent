"""Password hashing (scrypt) + JWT bearer auth."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, h_b64 = stored.split("$")
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(h_b64)
    except ValueError:
        return False
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(h, expected)


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.token_hours)
    return jwt.encode({"sub": str(user.id), "exp": exp}, settings.secret_key, algorithm="HS256")


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return db.get(User, int(data["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def optional_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                  db: Session = Depends(get_db)) -> User | None:
    return user_from_token(db, creds.credentials if creds else None)


def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise HTTPException(401, "Please log in to continue.")
    return user
