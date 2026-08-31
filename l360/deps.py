"""Shared FastAPI dependencies + tiny cross-router helpers (P3 split)."""
from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from l360 import auth
from l360.db import get_session
from l360.models import User


def _current_user(db: Session, l360_session: str | None) -> User | None:
    payload = auth.read_session_cookie(l360_session)
    if not payload:
        return None
    user = db.get(User, payload.get("uid"))
    if user is None or not user.active:
        return None
    # Sessions die when the password changes: the cookie carries a
    # fingerprint of the password hash it was issued against (P1-3).
    if payload.get("pw") != auth.password_fingerprint(user.password_hash):
        return None
    return user


def require_user(
    l360_session: str | None = Cookie(default=None), db: Session = Depends(get_session)
) -> User:
    user = _current_user(db, l360_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user




def _client_label(client) -> str:
    name = f"{client.guardian_first_name} {client.guardian_surname}"
    return f"{name} ({client.child_name})" if client.child_name else name


def _upsert_setting(db, key: str, value: str) -> None:
    from sqlalchemy import select

    from l360.models import AppSetting

    row = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if value:
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    elif row is not None:
        db.delete(row)
