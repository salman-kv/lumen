from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .db import Organization, get_db


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def make_jwt(org_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_hours)
    return jwt.encode({"sub": str(org_id), "typ": "admin", "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_org(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Organization:
    """Admin auth. Assistant tokens are NOT JWTs, so they can never pass this dependency."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please sign in to continue.")
    try:
        payload = jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"])
        if payload.get("typ") != "admin":
            raise ValueError
        org = db.get(Organization, int(payload["sub"]))
    except Exception:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    if not org:
        raise HTTPException(401, "Account not found.")
    return org
