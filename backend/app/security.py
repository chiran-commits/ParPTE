from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import SECRET_KEY, TOKEN_DAYS
from .db import SessionLocal, User, now

_ITER = 240_000


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), _ITER).hex()
    return f"pbkdf2${_ITER}${salt}${dk}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), int(it)).hex(), dk)
    except Exception:
        return False


def make_token(user: User) -> str:
    return jwt.encode({"sub": str(user.id), "exp": now() + timedelta(days=TOKEN_DAYS)}, SECRET_KEY, algorithm="HS256")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        uid = int(jwt.decode(cred.credentials, SECRET_KEY, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired — please sign in again")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user
