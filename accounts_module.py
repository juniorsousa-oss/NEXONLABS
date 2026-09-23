"""Autenticação por senha individual, sem exigir nome de usuário na entrada.

A senha inicial APP_PASSWORD cria a primeira conta administrativa UMA VEZ.
Depois disso, contas e hashes persistem no banco; APP_PASSWORD não é uma
senha mestra nem é consultada novamente no login.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, select, func
from sqlalchemy.orm import Mapped, mapped_column

ITERATIONS = 310_000
MAX_ACCOUNTS = 30

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "pbkdf2_sha256$" + str(ITERATIONS) + "$" + salt.hex() + "$" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        kind, rounds, salt, digest = stored.split("$")
        if kind != "pbkdf2_sha256":
            return False
        n = int(rounds)
        if not 200_000 <= n <= 1_000_000:
            return False
        trial = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), n)
        return hmac.compare_digest(trial, bytes.fromhex(digest))
    except (ValueError, TypeError, UnicodeError):
        return False

def setup_accounts(Base, engine, DB):
    class Account(Base):
        __tablename__ = "app_accounts"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(120), nullable=False)
        password_hash: Mapped[str] = mapped_column(String(250), nullable=False)
        role: Mapped[str] = mapped_column(String(24), default="usuario", nullable=False)
        active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        session_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    Base.metadata.create_all(engine, tables=[Account.__table__])
    with DB() as db:
        if db.scalar(select(func.count()).select_from(Account)) == 0:
            first_password = os.getenv("APP_PASSWORD", "")
            if not first_password:
                raise RuntimeError("Configure APP_PASSWORD para cadastrar o primeiro usuário administrador.")
            first_name = os.getenv("APP_DISPLAY_NAME", "Administrador").strip() or "Administrador"
            db.add(Account(name=first_name[:120], password_hash=hash_password(first_password), role="admin"))
            db.commit()
    return Account

def public(account):
    return {"id": account.id, "name": account.name, "role": account.role,
            "active": account.active, "created_at":account.created_at.isoformat() if account.created_at else None}

def find_by_password(db, Account, password: str):
    if not isinstance(password, str) or not password or len(password) > 256:
        return None
    accounts = db.scalars(select(Account).where(Account.active.is_(True)).order_by(Account.id)).all()
    matched = None
    for account in accounts:
        if verify_password(password, account.password_hash):
            matched = account
    return matched

def password_in_use(db, Account, password: str, skip_id=None):
    accounts=db.scalars(select(Account)).all()
    return any(verify_password(password, a.password_hash) for a in accounts if a.id!=skip_id)

def session_user(request, DB, Account):
    try:
        uid = int(request.session.get("account_id") or 0)
        version = int(request.session.get("account_version") or 0)
    except (TypeError, ValueError):
        return None
    if not uid or not version:
        return None
    with DB() as db:
        account = db.get(Account, uid)
        if account and account.active and account.session_version == version:
            return public(account)
    return None
