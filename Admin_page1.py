import base64
import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request, send_from_directory, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("LBAS_SECRET_KEY", "lbas-v8-secret")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("LBAS")

DB_FILES = {
    "books": "books.json",
    "users": "users.json",
    "admins": "admins.json",
    "transactions": "transactions.json",
    "ratings": "ratings.json",
    "config": "system_config.json",
    "tickets": "tickets.json",
    "categories": "categories.json",
    "home_cards": "home_cards.json",
    "news_posts": "news_posts.json",
    "registration_requests": "registration_requests.json",
    "reservation_transactions": "reservation_transaction.json",
    "admin_approval_record": "Admin_approval_record.json",
    "date_restricted": "Date_Restricted.json",
    "active_sessions": "active_sessions.json",
    "log_rec": "log_rec.json",
}

ACTIVE_SESSIONS = {}
_db_lock = threading.RLock()
SESSION_TIMEOUT_HOURS = 24


def get_db(key):
    with _db_lock:
        path = DB_FILES[key]
        try:
            if not os.path.exists(path):
                return {} if key in {"config", "date_restricted", "active_sessions", "log_rec"} else []
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {} if key in {"config", "date_restricted", "active_sessions", "log_rec"} else []


def save_db(key, data):
    with _db_lock:
        with open(DB_FILES[key], "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


def repair_statuses():
    for key in ["books", "transactions"]:
        rows = get_db(key)
        changed = False
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and "status" in row:
                    low = str(row.get("status", "")).strip().lower()
                    if low != row.get("status"):
                        row["status"] = low
                        changed = True
        if changed:
            save_db(key, rows)


def load_active_sessions():
    global ACTIVE_SESSIONS
    try:
        if os.path.exists("active_sessions.json"):
            raw = json.load(open("active_sessions.json", "r", encoding="utf-8"))
            cutoff = datetime.now() - timedelta(hours=SESSION_TIMEOUT_HOURS)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M")
            ACTIVE_SESSIONS = {
                k: v
                for k, v in raw.items()
                if isinstance(v, dict) and v.get("created_at", "") >= cutoff_str
            }
    except Exception as e:
        logger.error(f"Session load error: {e}")
        ACTIVE_SESSIONS = {}


def save_active_sessions():
    try:
        with open("active_sessions.json", "w", encoding="utf-8") as f:
            json.dump(ACTIVE_SESSIONS, f, indent=4)
    except Exception as e:
        logger.error(f"Session save error: {e}")


def find_any_user(s_id):
    sid = str(s_id or "").strip().lower()
    for a in get_db("admins"):
        if str(a.get("school_id", "")).strip().lower() == sid:
            r = dict(a)
            r["is_staff"] = True
            r["registry_origin"] = "admins.json"
            return r
    for u in get_db("users"):
        if str(u.get("school_id", "")).strip().lower() == sid:
            r = dict(u)
            r["is_staff"] = False
            r["registry_origin"] = "users.json"
            return r
    return None


def require_auth():
    token = request.headers.get("Authorization", "").strip()
    if not token:
        return None
    for s_id, sess in ACTIVE_SESSIONS.items():
        if isinstance(sess, dict):
            if sess.get("token") == token:
                return s_id
        elif sess == token:
            return s_id
    return None


def require_admin_session():
    if session.get("is_admin"):
        return session.get("admin_school_id", "admin")
    s_id = require_auth()
    if not s_id:
        return None
    user = find_any_user(s_id)
    if user and user.get("is_staff"):
        return s_id
    return None


def promote_next_in_queue(book_no):
    txs = get_db("transactions")
    books = get_db("books")
    has_reserved = any(str(t.get("book_no")) == str(book_no) and str(t.get("status", "")).lower() == "reserved" for t in txs)
    for b in books:
        if str(b.get("book_no")) == str(book_no):
            b["status"] = "reserved" if has_reserved else "available"
    save_db("books", books)


def initialize_system():
    os.makedirs("Profile", exist_ok=True)
    os.makedirs("LandingUploads", exist_ok=True)
    defaults = {
        "categories": ["General", "Mathematics", "Science", "Literature", "History"],
        "home_cards": [{"id": 1, "title": "", "body": ""}, {"id": 2, "title": "", "body": ""}, {"id": 3, "title": "", "body": ""}, {"id": 4, "title": "", "body": ""}],
        "news_posts": [],
        "registration_requests": [],
        "reservation_transactions": [],
        "admin_approval_record": [],
        "date_restricted": {},
        "active_sessions": {},
        "log_rec": {"month": "", "events": []},
        "ratings": [],
    }
    for k, p in DB_FILES.items():
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(defaults.get(k, []), f, indent=4)
    if not os.path.exists("Profile/default.png"):
        blank = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
        with open("Profile/default.png", "wb") as f:
            f.write(blank)
    load_active_sessions()
    repair_statuses()


@app.route("/")
def index_gateway():
    return render_template("Library_web_landing_page.html")


@app.route("/lbas")
def lbas_site():
    return render_template("LBAS.html")


@app.route("/books")
def books_page():
    return render_template("Book_page.html")


@app.route("/admin")
def admin_page():
    return render_template("admin_dashboard.html")


@app.route('/LandingUploads/<path:filename>')
def serve_landing_upload(filename):
    return send_from_directory('LandingUploads', filename)


@app.route('/Profile/<path:filename>')
def profile_upload(filename):
    return send_from_directory('Profile', filename)


@app.route('/api/books')
def api_books():
    return jsonify(get_db("books"))


@app.route('/api/users')
def api_users():
    return jsonify(get_db("users"))


@app.route('/api/admins')
def api_admins():
    return jsonify(get_db("admins"))


@app.route('/api/transactions')
def api_transactions():
    sid = require_auth()
    if not sid:
        return jsonify([])
    return jsonify(get_db("transactions"))


@app.route('/api/user/<s_id>')
def api_user(s_id):
    u = find_any_user(s_id)
    if not u:
        return jsonify({"success": False}), 404
    return jsonify(u)


def _build_shared():
    return {
        "get_db": get_db,
        "save_db": save_db,
        "find_any_user": find_any_user,
        "require_auth": require_auth,
        "require_admin_session": require_admin_session,
        "ACTIVE_SESSIONS": ACTIVE_SESSIONS,
        "save_active_sessions": save_active_sessions,
        "_db_lock": _db_lock,
        "promote_next_in_queue": promote_next_in_queue,
        "SESSION_TIMEOUT_HOURS": SESSION_TIMEOUT_HOURS,
        "secure_filename": secure_filename,
        "datetime": datetime,
        "timedelta": timedelta,
        "uuid": uuid,
        "os": os,
        "re": re,
        "session": session,
        "logger": logger,
    }


from api.API_auth import auth_bp, init_auth
from api.API_books import books_bp, init_books
from api.API_content import content_bp, init_content
from api.API_admin import admin_bp, init_admin

initialize_system()
shared = _build_shared()
init_auth(shared)
init_books(shared)
init_content(shared)
init_admin(shared)
app.register_blueprint(auth_bp)
app.register_blueprint(books_bp)
app.register_blueprint(content_bp)
app.register_blueprint(admin_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
