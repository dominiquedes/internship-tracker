import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
import requests
from flask import jsonify, request
from psycopg.rows import dict_row

from auth import require_user

STATUSES = (
    "applied",
    "in_process",
    "interview",
    "offered",
    "rejected",
)


def _database_url():
    url = (os.getenv("SB_DATABASE_URL") or "").strip()
    if not url:
        return None
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("sslmode", "require")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _connect():
    url = _database_url()
    if not url:
        return None
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=15)


def _pay_text(pay):
    if isinstance(pay, list):
        return "\n".join(item for item in pay if item) or None
    return pay or None


_COUNTRY = re.compile(r"^(usa|u\.s\.a\.|united states|us|uk|united kingdom)$", re.I)
_POSTAL = re.compile(r"^\d{5}(?:-\d{4})?$")


def _money(amount):
    digits = re.sub(r"[^\d.]", "", amount)
    if not digits:
        return amount
    number = float(digits)
    if number == int(number):
        return f"${int(number):,}"
    return f"${number:,.2f}"


def short_pay(pay):
    text = re.sub(r"\s+", " ", str(pay or "")).strip()
    if not text:
        return None
    match = re.search(
        r"(?:USD|\$)\s*([\d,]+(?:\.\d+)?)\s*[–\-]\s*(?:USD|\$)?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.I,
    )
    if not match:
        return text
    unit = ""
    unit_match = re.search(
        r"(?:/\s*|\bper\s+|\b)(year|hour|month|week|annum|annual|yearly)\b",
        text,
        re.I,
    )
    if unit_match:
        word = unit_match.group(1).lower()
        if word in {"annum", "annual", "yearly"}:
            word = "year"
        unit = f" / {word}"
    return f"{_money(match.group(1))}–{_money(match.group(2))}{unit}"


def _place(chunk):
    parts = [part.strip() for part in chunk.split(",") if part.strip()]
    kept = []
    for part in parts:
        if _COUNTRY.match(part) or _POSTAL.match(part) or re.match(r"^\d", part):
            continue
        kept.append(part)
    if len(kept) > 2:
        kept = kept[-2:]
    return ", ".join(kept)


def short_location(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return None
    places = []
    for chunk in re.split(r";|\s+\|\s+", text):
        place = _place(chunk)
        if place and place not in places:
            places.append(place)
    if not places:
        return text
    if len(places) == 1:
        return places[0]
    return f"{places[0]} + {len(places) - 1}"


def _status(value, default="applied"):
    status = str(value or "").strip() or default
    if status not in STATUSES:
        return None
    return status


def _item(row):
    created = row["created_at"]
    return {
        "id": str(row["id"]),
        "url": row["url"],
        "title": row["title"],
        "company": row["company"],
        "location": short_location(row["location"]),
        "summary": row["summary"],
        "pay": short_pay(row["pay"]),
        "status": row["status"] if row["status"] in STATUSES else "applied",
        "created_at": created.isoformat() if created else None,
    }


def register_internships(app, scrape_internship):
    @app.get("/internships")
    def list_internships():
        user, error = require_user()
        if error:
            return error

        connection = _connect()
        if connection is None:
            return jsonify({"error": "Database is not configured."}), 503

        try:
            with connection:
                rows = connection.execute(
                    """
                    select id, url, title, company, location, summary, pay, status, created_at
                    from public.internships
                    where user_id = %s
                    order by created_at desc
                    """,
                    (user.id,),
                ).fetchall()
        except psycopg.Error:
            return jsonify({"error": "Could not load internships."}), 500

        return jsonify({"internships": [_item(row) for row in rows]})

    @app.post("/internships")
    def add_internship():
        user, error = require_user()
        if error:
            return error
        if _database_url() is None:
            return jsonify({"error": "Database is not configured."}), 503

        body = request.get_json(silent=True) or {}
        url = str(body.get("url") or "").strip()
        if not url:
            return jsonify({"error": "Enter a link."}), 400
        status = _status(body.get("status"))
        if status is None:
            return jsonify({"error": "Choose where this application stands."}), 400

        try:
            info = scrape_internship(url)
        except ValueError as scrape_error:
            return jsonify({"error": str(scrape_error)}), 400
        except requests.RequestException:
            return jsonify({"error": "Could not read that page."}), 502

        try:
            with _connect() as connection:
                row = connection.execute(
                    """
                    insert into public.internships
                      (user_id, url, title, company, location, summary, pay, status)
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (user_id, url) do update set
                      title = excluded.title,
                      company = excluded.company,
                      location = excluded.location,
                      summary = excluded.summary,
                      pay = excluded.pay,
                      status = excluded.status
                    returning id, url, title, company, location, summary, pay, status, created_at
                    """,
                    (
                        user.id,
                        info.get("url") or url,
                        info.get("title"),
                        info.get("company"),
                        info.get("location"),
                        info.get("summary"),
                        _pay_text(info.get("pay")),
                        status,
                    ),
                ).fetchone()
                connection.commit()
        except psycopg.Error:
            return jsonify({"error": "Could not save that internship."}), 500

        return jsonify({"internship": _item(row)}), 201

    @app.patch("/internships/<internship_id>")
    def update_internship(internship_id):
        user, error = require_user()
        if error:
            return error

        connection = _connect()
        if connection is None:
            return jsonify({"error": "Database is not configured."}), 503

        body = request.get_json(silent=True) or {}
        assignments = []
        values = []
        if "status" in body:
            status = _status(body.get("status"), default="")
            if status is None:
                return jsonify({"error": "Choose where this application stands."}), 400
            assignments.append("status = %s")
            values.append(status)
        for field in ("title", "company", "pay", "location"):
            if field not in body:
                continue
            text = re.sub(r"\s+", " ", str(body.get(field) or "")).strip()
            assignments.append(f"{field} = %s")
            values.append(text or None)
        if not assignments:
            return jsonify({"error": "Nothing to update."}), 400

        values.extend((internship_id, user.id))
        try:
            with connection:
                row = connection.execute(
                    f"""
                    update public.internships
                    set {", ".join(assignments)}
                    where id = %s and user_id = %s
                    returning id, url, title, company, location, summary, pay, status, created_at
                    """,
                    values,
                ).fetchone()
        except psycopg.Error:
            return jsonify({"error": "Could not update that internship."}), 500

        if row is None:
            return jsonify({"error": "Internship not found."}), 404
        return jsonify({"internship": _item(row)})
