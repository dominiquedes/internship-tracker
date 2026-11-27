import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import jsonify, request
from supabase import create_client
from supabase_auth.errors import AuthError

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

URL_NAMES = (
    "SB_PROJECT_URL",
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
)
KEY_NAMES = (
    "SB_PUBLISHABLE_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
)


def _env_value(names):
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def _credentials():
    url = _env_value(URL_NAMES)
    key = _env_value(KEY_NAMES)
    if not url or not key:
        return None
    return url, key


def _client():
    found = _credentials()
    if not found:
        return None
    url, key = found
    return create_client(url, key)


def _missing_config_response():
    return jsonify({
        "error": (
            "Supabase is not configured. Save the project .env with a URL "
            f"({', '.join(URL_NAMES)}) and a key ({', '.join(KEY_NAMES)})."
        )
    }), 503


def _auth_error(error):
    status = getattr(error, "status", 400) or 400
    if status < 400 or status > 499:
        status = 400
    return jsonify({"error": error.message}), status


def _public_user(user):
    if user is None:
        return None
    metadata = user.user_metadata or {}
    name = metadata.get("full_name") or metadata.get("name")
    return {"id": user.id, "email": user.email, "name": name}


def _public_session(session):
    if session is None:
        return None
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
    }


def _bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header[7:].strip() or None


def _require_fields(body, fields):
    missing = [field for field in fields if not str(body.get(field) or "").strip()]
    if missing:
        return jsonify({"error": f"Missing {', '.join(missing)}"}), 400
    return None


def require_user():
    client = _client()
    if client is None:
        return None, _missing_config_response()

    token = _bearer_token()
    if not token:
        return None, (jsonify({"error": "Missing access token"}), 401)

    try:
        result = client.auth.get_user(token)
    except AuthError as error:
        return None, _auth_error(error)

    if result is None or result.user is None:
        return None, (jsonify({"error": "Not signed in"}), 401)
    return result.user, None


def register_auth(app):
    @app.post("/auth/signup")
    def signup():
        client = _client()
        if client is None:
            return _missing_config_response()

        body = request.get_json(silent=True) or {}
        invalid = _require_fields(body, ("name", "email", "password"))
        if invalid:
            return invalid

        name = str(body["name"]).strip()
        email = str(body["email"]).strip().lower()
        password = str(body["password"])
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters."}), 400

        try:
            result = client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {"full_name": name},
                    "email_redirect_to": "http://localhost:3000",
                },
            })
        except AuthError as error:
            return _auth_error(error)

        session = _public_session(result.session)
        payload = {"user": _public_user(result.user), "session": session}
        if session is None:
            payload["needs_confirmation"] = True
        return jsonify(payload)

    @app.post("/auth/login")
    def login():
        client = _client()
        if client is None:
            return _missing_config_response()

        body = request.get_json(silent=True) or {}
        invalid = _require_fields(body, ("email", "password"))
        if invalid:
            return invalid

        try:
            result = client.auth.sign_in_with_password({
                "email": str(body["email"]).strip().lower(),
                "password": str(body["password"]),
            })
        except AuthError as error:
            return _auth_error(error)

        if result.session is None:
            return jsonify({"error": "Confirm your email before logging in."}), 403

        return jsonify({
            "user": _public_user(result.user or result.session.user),
            "session": _public_session(result.session),
        })

    @app.get("/auth/me")
    def me():
        client = _client()
        if client is None:
            return _missing_config_response()

        token = _bearer_token()
        if not token:
            return jsonify({"error": "Missing access token"}), 401

        try:
            result = client.auth.get_user(token)
        except AuthError as error:
            return _auth_error(error)

        if result is None or result.user is None:
            return jsonify({"error": "Not signed in"}), 401
        return jsonify({"user": _public_user(result.user)})

    @app.post("/auth/logout")
    def logout():
        found = _credentials()
        token = _bearer_token()
        if found and token:
            url, key = found
            try:
                requests.post(
                    f"{url.rstrip('/')}/auth/v1/logout",
                    headers={"apikey": key, "Authorization": f"Bearer {token}"},
                    timeout=20,
                )
            except requests.RequestException:
                pass
        return jsonify({"ok": True})
