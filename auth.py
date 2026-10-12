"""Authentication helpers: password hashing, sessions and role guards."""
import functools
from datetime import datetime, timedelta

from flask import session, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

import config


# --------------------------- passwords ------------------------------- #
def hash_password(raw: str) -> str:
    return generate_password_hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return check_password_hash(hashed, raw)
    except Exception:
        return False


# --------------------------- lookups --------------------------------- #
def find_user(identifier: str):
    """Find a user by email OR mobile number."""
    import database as db
    if not identifier:
        return None
    identifier = identifier.strip()
    return db.query_one(
        "SELECT * FROM users WHERE lower(email)=lower(?) OR phone=?",
        (identifier, identifier))


def public_user(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "role": user["role"],
        "full_name": user["full_name"],
        "email": user["email"],
        "phone": user["phone"],
        "is_active": user["is_active"],
    }


# --------------------------- sessions -------------------------------- #
def start_session(user: dict):
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["role"] = user["role"]
    session["name"] = user["full_name"]


def end_session():
    session.clear()


def current_user():
    import database as db
    uid = session.get("user_id")
    if not uid:
        return None
    user = db.query_one("SELECT * FROM users WHERE user_id=?", (uid,))
    if user and not user["is_active"]:
        end_session()
        return None
    return user


def profile_for(user: dict):
    """Return the candidate/company profile row linked to a user."""
    import database as db
    if not user:
        return None
    if user["role"] == "candidate":
        return db.query_one(
            "SELECT * FROM candidates WHERE user_id=?", (user["user_id"],))
    if user["role"] == "company":
        return db.query_one(
            "SELECT * FROM companies WHERE user_id=?", (user["user_id"],))
    return None


# --------------------------- decorators ------------------------------ #
def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return jsonify({"error": "authentication required"}), 401
        return fn(*a, **kw)
    return wrapper


def role_required(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            user = current_user()
            if not user:
                return jsonify({"error": "authentication required"}), 401
            if user["role"] not in roles:
                return jsonify({"error": "forbidden for role '%s'" % user["role"]}), 403
            return fn(*a, **kw)
        return wrapper
    return deco
