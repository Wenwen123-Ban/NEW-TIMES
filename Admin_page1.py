import os
import json
import uuid
import logging
import sys
import operator
import random  # REQUIRED for Ticket Codes
import re
import string  # REQUIRED for Ticket Codes
import threading
import pymysql
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    redirect,
    url_for,
    make_response,
    session,
)
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("LBAS_SECRET_KEY", "lbas-admin-session-secret")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("LBAS_Command_Center")

_db_write_lock = threading.RLock()
PROFILE_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Profile"
)
CREATORS_PROFILE_DB = "creators_profiles.json"
LANDING_UPLOAD_FOLDER = "LandingUploads"
app.config["UPLOAD_FOLDER"] = PROFILE_FOLDER
app.config["LANDING_UPLOAD_FOLDER"] = LANDING_UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

if not os.path.exists(PROFILE_FOLDER):
    os.makedirs(PROFILE_FOLDER)
    logger.info(f"SYSTEM INIT: Created secure profile storage at ./{PROFILE_FOLDER}")

if not os.path.exists(LANDING_UPLOAD_FOLDER):
    os.makedirs(LANDING_UPLOAD_FOLDER)
    logger.info(f"SYSTEM INIT: Created landing uploads storage at ./{LANDING_UPLOAD_FOLDER}")

# Database Map: Full restoration of all required DBs
DB_FILES = {
    "books": "books.json",
    "admins": "admins.json",
    "users": "users.json",
    "transactions": "transactions.json",
    "config": "system_config.json",
    "tickets": "tickets.json",  # Password Recovery Registry
    "categories": "categories.json",
    "date_restricted": "Date_Restricted.json",
    "reservation_transactions": "reservation_transaction.json",
    "admin_approval_record": "Admin_approval_record.json",
    "registration_requests": "registration_requests.json",
    "log_rec": "log_rec.json",
    "home_cards": "home_cards.json",
    "news_posts": "news_posts.json",
}

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "lbas_db",
    "charset": "utf8mb4",
}

ACTIVE_SESSIONS = {}
SESSION_TIMEOUT_HOURS = 2


def require_auth():
    token = request.headers.get("Authorization")
    if not token:
        return None

    to_delete = []
    for user_id, session in list(ACTIVE_SESSIONS.items()):
        if isinstance(session, dict) and session.get("token") == token:
            if datetime.now() < session.get("expires", datetime.min):
                return user_id
            to_delete.append(user_id)

    for uid in to_delete:
        del ACTIVE_SESSIONS[uid]

    return None


def require_admin_session():
    admin_id = str(session.get("admin_school_id", "")).strip().lower()
    if not admin_id or not session.get("is_admin", False):
        return None

    admin_profile = find_any_user(admin_id)
    if not admin_profile or not admin_profile.get("is_staff", False):
        session.clear()
        return None
    return admin_id


def is_session_valid(user_id, token):
    session = ACTIVE_SESSIONS.get(str(user_id).strip().lower())
    if not isinstance(session, dict) or session.get("token") != token:
        return False
    if datetime.now() >= session.get("expires", datetime.min):
        del ACTIVE_SESSIONS[str(user_id).strip().lower()]
        return False
    return True


def ensure_creators_profile_db():
    if not os.path.exists(CREATORS_PROFILE_DB):
        with open(CREATORS_PROFILE_DB, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)


def load_creators_profiles():
    ensure_creators_profile_db()
    try:
        with open(CREATORS_PROFILE_DB, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                normalized = {}
                for idx, entry in enumerate(data):
                    if isinstance(entry, dict):
                        slot_key = str(entry.get("slot") or f"legacy_{idx}")
                        normalized[slot_key] = entry
                return normalized
            return {}
    except Exception:
        return {}


def save_creators_profiles(data):
    ensure_creators_profile_db()
    with open(CREATORS_PROFILE_DB, "w", encoding="utf-8") as f:
        json.dump(data if isinstance(data, dict) else {}, f, indent=4, ensure_ascii=False)


def sanitize_creator_name(value):
    base = secure_filename(str(value or "").strip())
    return base[:80] or "creator"


def generate_request_id(prefix="REQ"):
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{rand}"


def save_profile_photo(photo, school_id):
    """Save uploaded profile pictures in ./Profile using predictable per-ID filenames."""
    saved_photo = "default.png"
    if not (photo and getattr(photo, "filename", "")):
        return saved_photo

    _, ext = os.path.splitext(photo.filename)
    ext = (ext or ".png").lower()
    if len(ext) > 10:
        ext = ".png"

    sid = secure_filename(str(school_id).strip().lower()) or "user"
    filename = f"{sid}_profile{ext}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    photo.save(file_path)
    return filename


def save_post_image(uploaded_file):
    """Save uploaded landing/news media in ./Profile and return the filename."""
    if not (uploaded_file and getattr(uploaded_file, "filename", "")):
        return None

    original_name = secure_filename(uploaded_file.filename)
    if not original_name:
        return None

    _, ext = os.path.splitext(original_name)
    ext = (ext or "").lower()
    allowed_ext = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
    if ext not in allowed_ext:
        return None

    filename = f"news_{uuid.uuid4().hex[:16]}{ext}"
    uploaded_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return filename


def create_account_entry(target_db_key, category_name, name, school_id, password, photo):
    s_id = str(school_id or "").strip().lower()
    if not name or not s_id or not password:
        return False, "Missing required fields"

    if find_any_user(s_id):
        return False, "ID Exists"

    saved_photo = save_profile_photo(photo, s_id)
    registry = get_db(target_db_key)
    if not isinstance(registry, list):
        registry = []

    registry.append(
        {
            "name": str(name).strip(),
            "school_id": s_id,
            "password": password,
            "category": category_name,
            "photo": saved_photo,
            "status": "approved",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "phone_number": "",
        }
    )
    save_db(target_db_key, registry)
    return True, saved_photo


def initialize_system():
    logger.info("SYSTEM INIT: verifying database integrity...")
    ensure_creators_profile_db()
    default_path = os.path.join(PROFILE_FOLDER, "default.png")
    if not os.path.exists(default_path):
        import base64

        blank = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
            "HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAA"
            "SUVORK5CYII="
        )
        with open(default_path, "wb") as f:
            f.write(blank)
    for key, file_path in DB_FILES.items():
        if not os.path.exists(file_path):
            if key == "config":
                initial_data = {
                    "system_version": "7.2 Beta",
                    "last_reboot": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            elif key == "categories":
                initial_data = ["General", "Mathematics", "Science", "Literature"]
            elif key == "date_restricted":
                initial_data = {}
            elif key == "log_rec":
                initial_data = {
                    "month": datetime.now().strftime("%Y-%m"),
                    "events": [],
                }
            else:
                initial_data = []
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=4)

    # Remove legacy feedback file if it exists.
    if os.path.exists("ratings.json"):
        os.remove("ratings.json")

    # Ensure categories are available and in sync with book data
    sync_categories_with_books()

    # MIGRATION: Ensure status fields exist
    users = get_db("users")
    changed = False
    for u in users:
        if "status" not in u:
            u["status"] = "approved"
            changed = True
    if changed:
        save_db("users", users)

    # MIGRATION: Ensure phone_number exists for users/admins
    for reg_key in ["users", "admins"]:
        members = get_db(reg_key)
        registry_changed = False
        for member in members:
            if "phone_number" not in member:
                member["phone_number"] = ""
                registry_changed = True
        if registry_changed:
            save_db(reg_key, members)

    # MIGRATION: Ensure every book has a non-empty status for LBAS rendering/actions.
    books = get_db("books")
    books_changed = False
    for book in books:
        if not isinstance(book, dict):
            continue
        status = str(book.get("status", "")).strip()
        if not status:
            book["status"] = "Available"
            books_changed = True
    if books_changed:
        save_db("books", books)

    # Ensure Root Admin exists
    admins = get_db("admins")
    if not admins:
        admins.append(
            {
                "name": "System Administrator",
                "school_id": "admin",
                "password": "admin",
                "category": "Staff",
                "photo": "default.png",
                "is_staff": True,
                "status": "approved",
                "phone_number": "",
                "created_at": "SYSTEM_INIT",
            }
        )
        save_db("admins", admins)

    # Ensure home cards always has 4 structured slots.
    raw_cards = get_db("home_cards")
    normalized_cards = _normalize_home_cards(raw_cards)
    if raw_cards != normalized_cards:
        save_db("home_cards", normalized_cards)

    # Ensure news posts use the expected schema list format.
    raw_news_posts = get_db("news_posts")
    normalized_news = _normalize_news_posts(raw_news_posts)
    if raw_news_posts != normalized_news:
        save_db("news_posts", normalized_news)


def get_db(key):
    table_map = {
        "books": "books",
        "admins": "admins",
        "users": "users",
        "transactions": "transactions",
        "config": "system_config",
        "tickets": "tickets",
        "categories": "categories",
        "date_restricted": "date_restricted",
        "reservation_transactions": "reservation_transactions",
        "admin_approval_record": "admin_approval_record",
        "registration_requests": "registration_requests",
        "log_rec": "log_rec",
        "home_cards": "home_cards",
        "news_posts": "news_posts",
    }

    def _parse_json(value, fallback):
        if isinstance(value, (dict, list)):
            return value
        if value is None:
            return fallback
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, type(fallback)) else fallback
        except Exception:
            return fallback

    conn = None
    try:
        table = table_map.get(key)
        if not table:
            return {} if key == "config" else []

        conn = get_db_connection()
        with conn.cursor() as cursor:
            if key == "config":
                cursor.execute("SELECT config_key, config_value FROM system_config")
                rows = cursor.fetchall() or []
                return {str(r.get("config_key", "")): r.get("config_value", "") for r in rows if r.get("config_key")}

            if key == "categories":
                cursor.execute("SELECT name FROM categories")
                rows = cursor.fetchall() or []
                return [str(r.get("name", "")).strip() for r in rows if str(r.get("name", "")).strip()]

            if key == "log_rec":
                cursor.execute("SELECT data FROM log_rec ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone() or {}
                return _parse_json(row.get("data"), {"month": _current_month_key(), "events": []})

            if key == "date_restricted":
                cursor.execute("SELECT data FROM date_restricted ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone() or {}
                return _parse_json(row.get("data"), {})

            if key == "transactions":
                cursor.execute(
                    """
                    SELECT *
                    FROM transactions
                    """
                )
                rows = cursor.fetchall() or []
                return [
                    {
                        "id": row.get("id"),
                        "book_no": row.get("book_no") or row.get("book_id", ""),
                        "school_id": row.get("borrower_id") or row.get("school_id") or row.get("user_id", ""),
                        "borrower_name": row.get("borrower_name", ""),
                        "status": row.get("status") or row.get("transaction_status", ""),
                        "date": row.get("date_borrowed") or row.get("date", ""),
                        "return_date": row.get("date_returned") or row.get("return_date", ""),
                        "expiry": row.get("due_date") or row.get("expiry", ""),
                        "pickup_schedule": row.get("pickup_schedule") or row.get("pickup_slot", ""),
                        "due_date_override": row.get("due_date_override", ""),
                        "request_id": row.get("request_id", ""),
                    }
                    for row in rows
                ]

            if key == "reservation_transactions":
                cursor.execute(
                    """
                    SELECT id, book_id, user_id, user_name, status,
                           pickup_slot, reserved_at, borrowed_by, borrowed_at
                    FROM reservation_transactions
                    """
                )
                rows = cursor.fetchall() or []
                return [
                    {
                        "id": row.get("id"),
                        "book_no": row.get("book_id", ""),
                        "school_id": row.get("user_id", ""),
                        "borrower_name": row.get("user_name", ""),
                        "status": row.get("status", ""),
                        "pickup_schedule": row.get("pickup_slot", ""),
                        "date": row.get("reserved_at", ""),
                        "borrowed_by": row.get("borrowed_by", ""),
                        "borrowed_at": row.get("borrowed_at", ""),
                    }
                    for row in rows
                ]

            if key == "admin_approval_record":
                cursor.execute(
                    "SELECT id, admin_id, action, target_id, details, timestamp FROM admin_approval_record"
                )
                rows = cursor.fetchall() or []
                parsed_rows = []
                for row in rows:
                    details = _parse_json(row.get("details"), {})
                    if isinstance(details, dict) and details:
                        parsed_rows.append(details)
                    else:
                        parsed_rows.append({k: row.get(k) for k in ["id", "admin_id", "action", "target_id", "details", "timestamp"]})
                return parsed_rows

            if key == "books":
                cursor.execute("SELECT id, book_no, title, author, category, status, created_at FROM books")
            elif key in {"admins", "users"}:
                cursor.execute(
                    f"SELECT school_id, name, password, category, photo, is_staff, status, phone_number, created_at FROM {table}"
                )
            elif key == "registration_requests":
                cursor.execute(
                    "SELECT id, name, school_id, password, category, photo, status, requested_at FROM registration_requests"
                )
            elif key == "tickets":
                cursor.execute("SELECT id, school_id, code, status, created_at, expiry FROM tickets")
            elif key == "home_cards":
                cursor.execute("SELECT id, title, body FROM home_cards")
            elif key == "news_posts":
                cursor.execute("SELECT id, title, summary, body, image_filename, author, date FROM news_posts")
            else:
                return []

            rows = cursor.fetchall() or []
            if key in {"admins", "users"}:
                for row in rows:
                    row["is_staff"] = bool(row.get("is_staff"))
            return rows
    except Exception as e:
        logger.error(f"DB READ ERROR ({key}): {e}")
        return {} if key == "config" else []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def save_db(key, data):
    table_map = {
        "books": "books",
        "admins": "admins",
        "users": "users",
        "transactions": "transactions",
        "config": "system_config",
        "tickets": "tickets",
        "categories": "categories",
        "date_restricted": "date_restricted",
        "reservation_transactions": "reservation_transactions",
        "admin_approval_record": "admin_approval_record",
        "registration_requests": "registration_requests",
        "log_rec": "log_rec",
        "home_cards": "home_cards",
        "news_posts": "news_posts",
    }

    with _db_write_lock:
        conn = None
        try:
            table = table_map.get(key)
            if not table:
                return

            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table}")

                if key == "config":
                    if isinstance(data, dict):
                        for cfg_key, cfg_value in data.items():
                            cursor.execute(
                                "INSERT INTO system_config (config_key, config_value) VALUES (%s, %s)",
                                (str(cfg_key), str(cfg_value)),
                            )

                elif key == "categories":
                    for name in (data or []):
                        clean_name = str(name or "").strip()
                        if clean_name:
                            cursor.execute("INSERT INTO categories (name) VALUES (%s)", (clean_name,))

                elif key == "log_rec":
                    payload = data if isinstance(data, dict) else {"month": _current_month_key(), "events": []}
                    cursor.execute("INSERT INTO log_rec (data) VALUES (%s)", (json.dumps(payload, ensure_ascii=False),))

                elif key == "date_restricted":
                    payload = data if isinstance(data, dict) else {}
                    cursor.execute("INSERT INTO date_restricted (data) VALUES (%s)", (json.dumps(payload, ensure_ascii=False),))

                elif key == "books":
                    for row in (data or []):
                        cursor.execute(
                            "INSERT INTO books (book_no, title, author, category, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                            (
                                row.get("book_no", ""),
                                row.get("title", ""),
                                row.get("author", ""),
                                row.get("category", ""),
                                row.get("status", ""),
                                row.get("created_at", ""),
                            ),
                        )

                elif key in {"admins", "users"}:
                    for row in (data or []):
                        cursor.execute(
                            f"INSERT INTO {table} (school_id, name, password, category, photo, is_staff, status, phone_number, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                row.get("school_id", ""),
                                row.get("name", ""),
                                row.get("password", ""),
                                row.get("category", ""),
                                row.get("photo", "default.png"),
                                1 if bool(row.get("is_staff")) else 0,
                                row.get("status", "approved"),
                                row.get("phone_number", ""),
                                row.get("created_at", ""),
                            ),
                        )

                elif key == "transactions":
                    for row in (data or []):
                        cursor.execute(
                            "INSERT INTO transactions (book_no, borrower_id, borrower_name, status, date_borrowed, date_returned, due_date, pickup_schedule, due_date_override) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                row.get("book_no", ""),
                                row.get("school_id", ""),
                                row.get("borrower_name", ""),
                                row.get("status", ""),
                                row.get("date", ""),
                                row.get("return_date", ""),
                                row.get("expiry", ""),
                                row.get("pickup_schedule", ""),
                                row.get("due_date_override", ""),
                            ),
                        )

                elif key == "reservation_transactions":
                    for row in (data or []):
                        cursor.execute(
                            "INSERT INTO reservation_transactions (book_id, user_id, user_name, status, pickup_slot, reserved_at, borrowed_by, borrowed_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                row.get("book_no", ""),
                                row.get("school_id", ""),
                                row.get("borrower_name", ""),
                                row.get("status", ""),
                                row.get("pickup_schedule", ""),
                                row.get("date", ""),
                                row.get("borrowed_by", ""),
                                row.get("borrowed_at", ""),
                            ),
                        )

                elif key == "registration_requests":
                    for row in (data or []):
                        cursor.execute(
                            "INSERT INTO registration_requests (name, school_id, password, category, photo, status, requested_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (
                                row.get("name", ""),
                                row.get("school_id", ""),
                                row.get("password", ""),
                                row.get("category", ""),
                                row.get("photo", "default.png"),
                                row.get("status", "pending"),
                                row.get("requested_at", datetime.now().strftime("%Y-%m-%d %H:%M")),
                            ),
                        )

                elif key == "tickets":
                    for row in (data or []):
                        cursor.execute(
                            "INSERT INTO tickets (school_id, code, status, created_at, expiry) VALUES (%s, %s, %s, %s, %s)",
                            (
                                row.get("school_id", ""),
                                row.get("code", ""),
                                row.get("status", ""),
                                row.get("created_at", ""),
                                row.get("expiry", ""),
                            ),
                        )

                elif key == "admin_approval_record":
                    for row in (data or []):
                        payload = row if isinstance(row, dict) else {"value": row}
                        cursor.execute(
                            "INSERT INTO admin_approval_record (admin_id, action, target_id, details, timestamp) VALUES (%s, %s, %s, %s, %s)",
                            (
                                str(payload.get("approved_by", "system") or "system"),
                                str(payload.get("action", payload.get("status", "record")) or "record"),
                                str(payload.get("school_id", payload.get("target_id", "")) or ""),
                                json.dumps(payload, ensure_ascii=False),
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            ),
                        )

                elif key == "home_cards":
                    for row in (data or []):
                        cursor.execute(
                            "INSERT INTO home_cards (id, title, body) VALUES (%s, %s, %s)",
                            (row.get("id"), row.get("title", ""), row.get("body", "")),
                        )

                elif key == "news_posts":
                    for row in (data or []):
                        cursor.execute(
                            "INSERT INTO news_posts (id, title, summary, body, image_filename, author, date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (
                                row.get("id", uuid.uuid4().hex),
                                row.get("title", ""),
                                row.get("summary", ""),
                                row.get("body", ""),
                                row.get("image_filename"),
                                row.get("author", ""),
                                row.get("date", datetime.now().strftime("%Y-%m-%d %H:%M")),
                            ),
                        )

                conn.commit()
        except Exception as e:
            logger.error(f"DB WRITE ERROR ({key}): {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()


def get_db_connection():
    return pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **MYSQL_CONFIG)


def _current_month_key():
    return datetime.now().strftime("%Y-%m")


def _ensure_log_registry(reset_if_new_month=True):
    raw = get_db("log_rec")
    if not isinstance(raw, dict):
        raw = {"month": _current_month_key(), "events": []}

    month_key = str(raw.get("month", "")).strip()
    if not month_key:
        month_key = _current_month_key()

    if not isinstance(raw.get("events"), list):
        raw["events"] = []

    if reset_if_new_month and month_key != _current_month_key():
        raw = {"month": _current_month_key(), "events": []}
        save_db("log_rec", raw)

    return raw


def record_system_event(event_type, school_id=""):
    payload = _ensure_log_registry(reset_if_new_month=True)
    payload.setdefault("events", []).append(
        {
            "event": str(event_type).strip().lower(),
            "school_id": str(school_id or "").strip().lower(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    save_db("log_rec", payload)


def _monthly_activity_summary():
    payload = _ensure_log_registry(reset_if_new_month=True)
    month_key = payload.get("month", _current_month_key())
    events = payload.get("events", [])
    login_daily = {}
    reserve_daily = {}

    for row in events:
        stamp = _parse_transaction_date(row.get("timestamp"))
        if not stamp:
            continue
        day = stamp.strftime("%Y-%m-%d")
        event_name = str(row.get("event", "")).strip().lower()
        if event_name == "login":
            login_daily[day] = login_daily.get(day, 0) + 1
        elif event_name == "reserve":
            reserve_daily[day] = reserve_daily.get(day, 0) + 1

    calendar_days = []
    try:
        month_start = datetime.strptime(f"{month_key}-01", "%Y-%m-%d")
    except ValueError:
        month_start = datetime.now().replace(day=1)

    cursor = month_start
    while cursor.month == month_start.month:
        day = cursor.strftime("%Y-%m-%d")
        calendar_days.append(
            {
                "day": day,
                "login": login_daily.get(day, 0),
                "reserve": reserve_daily.get(day, 0),
            }
        )
        cursor += timedelta(days=1)

    return {
        "month": month_key,
        "totals": {
            "login": sum(login_daily.values()),
            "reserve": sum(reserve_daily.values()),
        },
        "days": calendar_days,
    }


def _normalize_date_only(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _ph_holiday_map(year):
    # Common Philippine national holidays (fixed-date set).
    fixed = {
        "01-01": "New Year's Day",
        "04-09": "Araw ng Kagitingan",
        "05-01": "Labor Day",
        "06-12": "Independence Day",
        "08-21": "Ninoy Aquino Day",
        "08-26": "National Heroes Day",
        "11-01": "All Saints' Day",
        "11-30": "Bonifacio Day",
        "12-08": "Feast of the Immaculate Conception",
        "12-25": "Christmas Day",
        "12-30": "Rizal Day",
    }
    return {f"{year}-{md}": title for md, title in fixed.items()}


def _load_manual_date_restrictions():
    raw = get_db("date_restricted")
    if isinstance(raw, dict):
        return raw
    return {}


def _save_manual_date_restrictions(payload):
    save_db("date_restricted", payload if isinstance(payload, dict) else {})


def _get_date_restriction_status(date_str):
    date_key = _normalize_date_only(date_str)
    if not date_key:
        return {"date": "", "restricted": False, "reason": "", "source": "invalid"}

    day = datetime.strptime(date_key, "%Y-%m-%d")
    auto_restricted = day.weekday() >= 5
    auto_reason = "Weekend (Saturday/Sunday)"

    holidays = _ph_holiday_map(day.year)
    if date_key in holidays:
        auto_restricted = True
        auto_reason = f"Philippine National Holiday: {holidays[date_key]}"

    manual = _load_manual_date_restrictions().get(date_key, {})
    action = str(manual.get("action", "")).strip().lower()
    reason = str(manual.get("reason", "")).strip()

    if action == "lift":
        return {
            "date": date_key,
            "restricted": False,
            "reason": reason,
            "source": "manual_lift",
        }
    if action == "ban":
        return {
            "date": date_key,
            "restricted": True,
            "reason": reason,
            "source": "manual_ban",
        }

    return {
        "date": date_key,
        "restricted": auto_restricted,
        "reason": auto_reason if auto_restricted else "",
        "source": "auto" if auto_restricted else "open",
    }


def sanitize_category_name(value):
    clean = str(value or "").strip()
    return clean[:80] if clean else ""


def get_categories():
    categories = get_db("categories")
    if not isinstance(categories, list):
        categories = []

    clean = []
    for c in categories:
        normalized = sanitize_category_name(c)
        if normalized and normalized not in clean:
            clean.append(normalized)

    for default in ["General", "Mathematics", "Science", "Literature"]:
        if default not in clean:
            clean.append(default)
    return clean


def save_categories(categories):
    unique = []
    for c in categories:
        normalized = sanitize_category_name(c)
        if normalized and normalized not in unique:
            unique.append(normalized)
    save_db("categories", unique)
    return unique


def sync_categories_with_books():
    categories = get_categories()
    for b in get_db("books"):
        cat = sanitize_category_name(b.get("category"))
        if cat and cat not in categories:
            categories.append(cat)
    return save_categories(categories)


def find_any_user(s_id):
    s_id = str(s_id).strip().lower()
    if not s_id:
        return None

    for admin in get_db("admins"):
        if str(admin.get("school_id", "")).strip().lower() == s_id:
            result = dict(admin)
            result["registry_origin"] = "admins.json"
            result["is_staff"] = True
            return result

    for student in get_db("users"):
        if str(student.get("school_id", "")).strip().lower() == s_id:
            result = dict(student)
            result["registry_origin"] = "users.json"
            result["is_staff"] = False
            return result
    return None


def is_mobile_request():
    ua = request.headers.get("User-Agent", "").lower()
    return any(
        x in ua for x in ["mobile", "android", "iphone", "ipad", "windows phone"]
    )


def _pickup_sort_key(tx):
    raw = str(tx.get("pickup_schedule", "") or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return datetime.max


def promote_next_in_queue(book_no):
    transactions = get_db("transactions")
    books = get_db("books")
    queue = [
        t
        for t in transactions
        if t.get("book_no") == book_no
        and str(t.get("status", "")).strip().lower() == "reserved"
        and t.get("pickup_schedule")
    ]

    if not queue:
        for b in books:
            if b.get("book_no") == book_no:
                b["status"] = "Available"
        save_db("books", books)
        return

    queue.sort(key=_pickup_sort_key)
    for b in books:
        if b.get("book_no") == book_no:
            b["status"] = "Reserved"
    save_db("books", books)


def check_missed_pickups():
    transactions = get_db("transactions")
    now = datetime.now()
    changed = False
    affected_books = set()

    for tx in transactions:
        if str(tx.get("status", "")).strip().lower() != "reserved":
            continue

        raw = str(tx.get("pickup_schedule", "") or "").strip()
        if not raw:
            continue

        pickup_dt = None
        date_only = False
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                pickup_dt = datetime.strptime(raw, fmt)
                if fmt == "%Y-%m-%d":
                    date_only = True
                break
            except ValueError:
                continue

        if not pickup_dt:
            continue

        if date_only:
            pickup_dt = pickup_dt.replace(hour=17, minute=0)

        grace = pickup_dt + timedelta(minutes=30)
        if now <= grace:
            continue

        already_borrowed = any(
            t.get("book_no") == tx.get("book_no")
            and str(t.get("school_id", "")).strip().lower()
            == str(tx.get("school_id", "")).strip().lower()
            and str(t.get("status", "")).strip().lower() in ("borrowed", "converted")
            for t in transactions
        )

        if not already_borrowed:
            tx["status"] = "Missed"
            tx["missed_at"] = now.strftime("%Y-%m-%d %H:%M")
            affected_books.add(tx.get("book_no"))
            changed = True

    if changed:
        save_db("transactions", transactions)
        for book_no in affected_books:
            promote_next_in_queue(book_no)


def run_auto_sync_engine():
    """
    CRITICAL SYNC ENGINE (RESTORED):
    1. Manages Book Reservations (Expires them after 30 mins).
    2. Manages Ticket Requests (Deletes them after 5 mins).
    3. Manages Overdue Calculations.
    """
    check_missed_pickups()
    books = get_db("books")
    transactions = get_db("transactions")
    tickets = get_db("tickets")
    now = datetime.now()
    changes_made = False

    # 1. Sync Reservations (legacy expiry support only)
    for t in transactions:
        if not isinstance(t, dict):
            continue
        if str(t.get("status", "")).strip() != "Reserved":
            continue
        expiry_value = str(t.get("expiry", "")).strip()
        if not expiry_value:
            continue
        try:
            if now > datetime.strptime(expiry_value, "%Y-%m-%d %H:%M"):
                t["status"] = "Expired"
                for b in books:
                    if isinstance(b, dict) and b.get("book_no") == t.get("book_no"):
                        b["status"] = "Available"
                        changes_made = True
        except ValueError:
            continue

    # 2. Sync Recovery Tickets (Cleanup expired)
    if isinstance(tickets, list) and tickets:
        initial_tickets = len(tickets)

        def _safe_ticket_valid(t):
            try:
                exp = t.get("expiry", "") if isinstance(t, dict) else ""
                if not exp:
                    return False
                return datetime.strptime(str(exp), "%Y-%m-%d %H:%M:%S") > now
            except Exception:
                return False

        tickets = [t for t in tickets if _safe_ticket_valid(t)]
        if len(tickets) != initial_tickets:
            save_db("tickets", tickets)

    if changes_made:
        save_db("books", books)
        save_db("transactions", transactions)

    return books


@app.route("/")
def index_gateway():
    return render_template("Library_web_landing_page.html")


@app.route("/admin")
def admin_site():
    # Pre-load data for dashboard
    return render_template(
        "admin_dashboard.html",
        books=run_auto_sync_engine(),
        users=get_db("users"),
        admins=get_db("admins"),
    )


@app.route("/lbas")
def lbas_site():
    return render_template("LBAS.html")


@app.route("/tablet")
def tablet_kiosk():
    return redirect(url_for("lbas_site"))


@app.route("/audit_users")
def audit_view():
    return redirect(url_for("admin_site"))




@app.route("/api/bulk_register", methods=["POST"])
def bulk_register():
    """
    SMART BULK IMPORTER:
    Handles '|', ',', or Space delimiters.
    Fixes the issue where 'LIT-001, Title' was failing.
    """
    try:
        data = request.json
        raw_text = data.get("text", "")
        category = sanitize_category_name(data.get("category", "General")) or "General"
        clear_first = data.get("clear_first", False)

        books = [] if clear_first else get_db("books")
        added = 0

        for line in raw_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # DELIMITER DETECTION
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
            elif "," in line:
                parts = [p.strip() for p in line.split(",", 1)]
            else:
                parts = line.split(maxsplit=1)

            if len(parts) >= 2:
                b_no = parts[0].strip().upper().replace(",", "")  # Clean ID
                title = parts[1].strip()

                # Duplicate Check
                if not any(b["book_no"] == b_no for b in books):
                    books.append(
                        {
                            "book_no": b_no,
                            "title": title,
                            "status": "Available",
                            "category": category,
                        }
                    )
                    added += 1

        save_db("books", books)
        categories = sync_categories_with_books()
        # Return keys for both legacy and new frontend versions
        return jsonify(
            {
                "success": True,
                "added": added,
                "items_added": added,
                "total_in_db": len(books),
                "categories": categories,
            }
        )
    except Exception as e:
        logger.error(f"Bulk Import Failed: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/register_student", methods=["POST"])
def api_register_student():
    name = request.form.get("name")
    school_id = request.form.get("school_id")
    password = request.form.get("password")
    photo = request.files.get("photo")

    ok, payload = create_account_entry(
        "users", "Student", name, school_id, password, photo
    )
    if not ok:
        return jsonify({"success": False, "message": payload}), 400
    return jsonify({"success": True, "photo": payload})


@app.route("/api/register_librarian", methods=["POST"])
def api_register_librarian():
    name = request.form.get("name")
    school_id = request.form.get("school_id")
    password = request.form.get("password")
    photo = request.files.get("photo")

    ok, payload = create_account_entry(
        "admins", "Staff", name, school_id, password, photo
    )
    if not ok:
        return jsonify({"success": False, "message": payload}), 400
    return jsonify({"success": True, "photo": payload})


@app.route("/api/register_request", methods=["POST"])
def api_register_request():
    name = request.form.get("name")
    school_id = str(request.form.get("school_id", "")).strip().lower()
    password = request.form.get("password")
    role = "student"
    photo = request.files.get("photo")

    if not name or not school_id or not password:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
    if find_any_user(school_id):
        return jsonify({"success": False, "message": "ID Exists"}), 400

    requests = get_db("registration_requests")
    if not isinstance(requests, list):
        requests = []

    pending_for_id = next(
        (
            row
            for row in requests
            if str(row.get("school_id", "")).strip().lower() == school_id
            and str(row.get("status", "pending")).strip().lower() == "pending"
        ),
        None,
    )
    if pending_for_id:
        return jsonify({"success": False, "message": "Existing pending request"}), 400

    req_id = generate_request_id("REG")
    saved_photo = save_profile_photo(photo, school_id)

    requests.append(
        {
            "request_id": req_id,
            "name": str(name).strip(),
            "school_id": school_id,
            "password": password,
            "role": role,
            "photo": saved_photo,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    save_db("registration_requests", requests)
    return jsonify({"success": True, "request_id": req_id})


@app.route("/api/admin/registration-requests")
def api_admin_get_registration_requests():
    if not require_admin_session():
        return jsonify({"success": False, "message": "Admin authorization required"}), 401
    rows = get_db("registration_requests")
    if not isinstance(rows, list):
        rows = []
    return jsonify(rows)


@app.route("/api/admin/registration-requests/<request_id>/decision", methods=["POST"])
def api_admin_decide_registration_request(request_id):
    admin_id = require_admin_session()
    if not admin_id:
        return jsonify({"success": False, "message": "Admin authorization required"}), 401

    decision = str((request.get_json(silent=True) or {}).get("decision", "")).strip().lower()
    if decision not in ["approve", "reject"]:
        return jsonify({"success": False, "message": "Invalid decision"}), 400

    rows = get_db("registration_requests")
    if not isinstance(rows, list):
        rows = []

    target = next((row for row in rows if row.get("request_id") == request_id), None)
    if not target:
        return jsonify({"success": False, "message": "Request not found"}), 404
    if str(target.get("status", "pending")).lower() != "pending":
        return jsonify({"success": False, "message": "Request already resolved"}), 400

    target["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    target["reviewed_by"] = admin_id

    if decision == "reject":
        target["status"] = "rejected"
        save_db("registration_requests", rows)
        return jsonify({"success": True, "decision": "rejected"})

    role = str(target.get("role", "student")).strip().lower()
    db_key = "admins" if role == "admin" else "users"
    category = "Staff" if role == "admin" else "Student"

    ok, message = create_account_entry(
        db_key,
        category,
        target.get("name"),
        target.get("school_id"),
        target.get("password"),
        None,
    )
    if not ok:
        return jsonify({"success": False, "message": message}), 400

    registry = get_db(db_key)
    if isinstance(registry, list):
        account = next(
            (
                row
                for row in registry
                if str(row.get("school_id", "")).strip().lower()
                == str(target.get("school_id", "")).strip().lower()
            ),
            None,
        )
        if account and target.get("photo"):
            account["photo"] = target["photo"]
            save_db(db_key, registry)

    target["status"] = "approved"
    save_db("registration_requests", rows)
    return jsonify({"success": True, "decision": "approved"})


@app.route("/api/request_reset", methods=["POST"])
def api_request_reset():
    """Step 1: Student requests ticket."""
    s_id = str(request.json.get("school_id", "")).strip().lower()
    if not find_any_user(s_id):
        return jsonify({"success": False, "message": "ID not found"}), 404

    tickets = get_db("tickets")
    tickets = [t for t in tickets if t["school_id"] != s_id]  # Clean old requests

    tickets.append(
        {
            "school_id": s_id,
            "status": "pending",
            "code": None,
            "expiry": (datetime.now() + timedelta(minutes=5)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
    )
    save_db("tickets", tickets)
    return jsonify({"success": True})


@app.route("/api/check_ticket_status", methods=["POST"])
def api_check_ticket():
    """Step 2: Mobile checks if approved."""
    s_id = str(request.json.get("school_id", "")).strip().lower()
    tickets = get_db("tickets")
    ticket = next((t for t in tickets if t["school_id"] == s_id), None)

    if ticket and ticket["status"] == "approved":
        return jsonify({"status": "approved", "code": ticket["code"]})
    return jsonify({"status": "pending"})


@app.route("/api/admin/tickets")
def api_get_tickets():
    """Step 3: Dashboard gets list."""
    return jsonify(get_db("tickets"))


@app.route("/api/admin/approve_ticket", methods=["POST"])
def api_approve_ticket():
    """Step 4: Admin approves & generates code."""
    s_id = request.json.get("school_id")
    tickets = get_db("tickets")
    for t in tickets:
        if t["school_id"] == s_id:
            t["status"] = "approved"
            t["code"] = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
            save_db("tickets", tickets)
            return jsonify({"success": True, "code": t["code"]})
    return jsonify({"success": False}), 404


@app.route("/api/finalize_reset", methods=["POST"])
def api_finalize_reset():
    """Step 5: Apply new password."""
    data = request.json
    s_id = str(data.get("school_id", "")).strip().lower()
    new_pwd = data.get("new_password")
    code = data.get("code")

    tickets = get_db("tickets")
    ticket = next(
        (t for t in tickets if t["school_id"] == s_id and t["code"] == code), None
    )

    if ticket:
        # Update user registry
        for db in ["users", "admins"]:
            registry = get_db(db)
            updated = False
            for u in registry:
                if u["school_id"] == s_id:
                    u["password"] = new_pwd
                    updated = True
            if updated:
                save_db(db, registry)

        # Consume ticket
        save_db("tickets", [t for t in tickets if t["school_id"] != s_id])
        return jsonify({"success": True})
    return jsonify({"success": False}), 401




@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    s_id = str(data.get("school_id", "")).strip().lower()
    pwd = data.get("password")
    id_only = bool(data.get("id_only", False))

    user = find_any_user(s_id)
    if not user:
        registration_requests = get_db("registration_requests")
        if isinstance(registration_requests, list):
            pending_request = next(
                (
                    row
                    for row in registration_requests
                    if str(row.get("school_id", "")).strip().lower() == s_id
                    and str(row.get("status", "pending")).strip().lower() == "pending"
                ),
                None,
            )
            if pending_request:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Your account still Pending for approval",
                        }
                    ),
                    401,
                )
        return jsonify({"success": False, "message": "ID not found"}), 404

    if user["status"] == "pending":
        return jsonify({"success": False, "message": "Account Pending Approval"}), 401

    if id_only and not user.get("is_staff", False):
        token = str(uuid.uuid4())
        ACTIVE_SESSIONS[s_id] = {
            "token": token,
            "expires": datetime.now() + timedelta(hours=SESSION_TIMEOUT_HOURS),
        }
        record_system_event("login", s_id)
        return jsonify({"success": True, "token": token, "profile": user})

    if user.get("password") == pwd:
        token = str(uuid.uuid4())
        ACTIVE_SESSIONS[s_id] = {
            "token": token,
            "expires": datetime.now() + timedelta(hours=SESSION_TIMEOUT_HOURS),
        }
        if user.get("is_staff", False):
            session["is_admin"] = True
            session["admin_school_id"] = s_id
        else:
            session.pop("is_admin", None)
            session.pop("admin_school_id", None)
        record_system_event("login", s_id)
        return jsonify({"success": True, "token": token, "profile": user})

    return jsonify({"success": False, "message": "Invalid Password"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    token = request.headers.get("Authorization")
    for user_id, active_session in list(ACTIVE_SESSIONS.items()):
        if isinstance(active_session, dict) and active_session.get("token") == token:
            del ACTIVE_SESSIONS[user_id]
            return jsonify({"success": True})
    return jsonify({"success": True})


@app.route("/api/admin/books")
def api_admin_get_books():
    if not require_admin_session():
        return jsonify({"success": False, "message": "Admin authorization required"}), 401
    return jsonify(run_auto_sync_engine())


@app.route("/api/admin/users")
def api_admin_get_users():
    if not require_admin_session():
        return jsonify({"success": False, "message": "Admin authorization required"}), 401
    return jsonify(get_db("users"))


@app.route("/api/admin/admins")
def api_admin_get_admins():
    if not require_admin_session():
        return jsonify({"success": False, "message": "Admin authorization required"}), 401
    return jsonify(get_db("admins"))


@app.route("/api/admin/transactions")
def api_admin_get_transactions():
    if not require_admin_session():
        return jsonify({"success": False, "message": "Admin authorization required"}), 401
    transactions = get_db("transactions")
    books = get_db("books")
    books_by_no = {
        str((b or {}).get("book_no", "")).strip().lower(): (b or {}).get("title", "")
        for b in (books if isinstance(books, list) else [])
        if isinstance(b, dict)
    }

    for tx in transactions if isinstance(transactions, list) else []:
        if not isinstance(tx, dict):
            continue
        book_ref = str(tx.get("book_no") or tx.get("book_id") or "").strip()
        tx["book_no"] = book_ref
        tx["title"] = books_by_no.get(book_ref.lower(), tx.get("title") or "Unknown Title")

    return jsonify(transactions if isinstance(transactions, list) else [])


@app.route("/api/admin/approval-records")
def api_admin_get_approval_records():
    if not require_admin_session():
        return jsonify({"success": False, "message": "Admin authorization required"}), 401

    records = get_db("admin_approval_record")
    if not isinstance(records, list):
        records = []
    return jsonify(records)


@app.route("/api/books")
def api_get_books():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    books = run_auto_sync_engine()
    if not isinstance(books, list):
        books = []

    normalized_books = []
    changed = False
    for book in books:
        if not isinstance(book, dict):
            continue
        status = str(book.get("status", "")).strip() or "Available"
        if status != book.get("status"):
            book["status"] = status
            changed = True
        normalized_books.append(book)

    if changed:
        save_db("books", books)
    return jsonify(normalized_books)


@app.route("/api/categories")
def api_get_categories():
    return jsonify(sync_categories_with_books())


@app.route("/api/categories", methods=["POST"])
def api_add_category():
    payload = request.get_json(silent=True) or {}
    category = sanitize_category_name(payload.get("category") or payload.get("name"))
    if not category:
        return jsonify({"success": False, "message": "Invalid category name"}), 400

    categories = get_categories()

    existing_lookup = {str(c).strip().lower() for c in categories}
    if category.lower() in existing_lookup:
        return jsonify({"success": True, "categories": categories, "created": False})

    categories.append(category)
    categories = save_categories(categories)
    return jsonify({"success": True, "categories": categories, "created": True})


@app.route("/api/categories/delete", methods=["POST"])
def api_delete_category():
    category = sanitize_category_name(request.json.get("category"))
    if not category:
        return jsonify({"success": False, "message": "Invalid category name"}), 400

    books_using = [
        b
        for b in get_db("books")
        if sanitize_category_name(b.get("category")) == category
    ]
    if books_using:
        return (
            jsonify(
                {"success": False, "message": "Category is in use by existing books"}
            ),
            400,
        )

    categories = [c for c in get_categories() if c != category]
    save_categories(categories)
    return jsonify({"success": True, "categories": categories})


@app.route("/api/delete_category", methods=["POST"])
def api_delete_category_cascade():
    books_snapshot = get_db("books")
    transactions_snapshot = get_db("transactions")
    categories_snapshot = get_categories()

    category = sanitize_category_name((request.json or {}).get("category"))
    if not category or category == "All Collections":
        return jsonify({"success": False, "message": "Invalid category name"}), 400

    try:
        books_to_delete = {
            b.get("book_no")
            for b in books_snapshot
            if sanitize_category_name(b.get("category")) == category
        }

        filtered_transactions = [
            t for t in transactions_snapshot if t.get("book_no") not in books_to_delete
        ]
        filtered_books = [
            b
            for b in books_snapshot
            if sanitize_category_name(b.get("category")) != category
        ]

        save_db("transactions", filtered_transactions)
        save_db("books", filtered_books)
        save_categories([c for c in categories_snapshot if c != category])

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"DELETE CATEGORY ERROR: {e}")
        save_db("transactions", transactions_snapshot)
        save_db("books", books_snapshot)
        save_categories(categories_snapshot)
        return jsonify({"success": False}), 500


@app.route("/api/users")
def api_get_users():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify(get_db("users"))


@app.route("/api/admins")
def api_get_admins():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify(get_db("admins"))


@app.route("/api/transactions")
def api_get_transactions():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    transactions = get_db("transactions")
    if not isinstance(transactions, list):
        transactions = []

    for tx in transactions:
        status = str(tx.get("status", "")).strip().lower()
        if status != "reserved":
            continue

        book_no = tx.get("book_no")
        book_queue = sorted(
            [
                t
                for t in transactions
                if t.get("book_no") == book_no
                and str(t.get("status", "")).strip().lower() == "reserved"
            ],
            key=_pickup_sort_key,
        )

        tx["queue_position"] = next(
            (
                i + 1
                for i, t in enumerate(book_queue)
                if str(t.get("school_id", "")).strip().lower()
                == str(tx.get("school_id", "")).strip().lower()
            ),
            None,
        )
        tx["queue_total"] = len(book_queue)
        tx["same_slot_conflict"] = (
            sum(
                1
                for t in book_queue
                if t.get("pickup_schedule") == tx.get("pickup_schedule")
            )
            > 1
        )
    return jsonify(transactions)


@app.route("/api/admin_approval_record")
def api_get_admin_approval_records():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    records = get_db("admin_approval_record")
    if not isinstance(records, list):
        records = []
    return jsonify(records)


@app.route("/api/user/<s_id>")
def api_get_specific_user(s_id):
    """Restored: Required for Tablet Kiosk to Scan User"""
    user = find_any_user(s_id)
    if user:
        return jsonify({"success": True, "profile": user})
    return jsonify({"success": False}), 404


@app.route("/api/update_book", methods=["POST"])
def api_update_book():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.json
    books = get_db("books")
    for b in books:
        if b["book_no"] == data["book_no"]:
            if "category" in data:
                data["category"] = sanitize_category_name(data["category"]) or "General"
            b.update({k: v for k, v in data.items() if k in b})
            save_db("books", books)
            sync_categories_with_books()
            return jsonify({"success": True})
    return jsonify({"success": False}), 404


@app.route("/api/delete_book", methods=["POST"])
def api_del_book():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.json
    books = [b for b in get_db("books") if b["book_no"] != data["book_no"]]
    save_db("books", books)
    sync_categories_with_books()
    return jsonify({"success": True})


@app.route("/api/update_member", methods=["POST"])
def api_update_member():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.json
    school_id = str(data.get("school_id", "")).strip().lower()
    name = str(data.get("name", "")).strip()
    target_type = str(data.get("type", "student")).strip().lower()

    if not school_id or not name:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    db_key = "admins" if target_type == "admin" else "users"
    records = get_db(db_key)
    for row in records:
        if str(row.get("school_id", "")).strip().lower() == school_id:
            row["name"] = name
            save_db(db_key, records)
            return jsonify({"success": True})
    return jsonify({"success": False, "message": "Member not found"}), 404


@app.route("/api/delete_member", methods=["POST"])
def api_delete_member():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.json
    school_id = str(data.get("school_id", "")).strip().lower()
    target_type = str(data.get("type", "student")).strip().lower()

    if not school_id:
        return jsonify({"success": False, "message": "Missing school_id"}), 400

    db_key = "admins" if target_type == "admin" else "users"
    records = get_db(db_key)
    filtered = [
        r for r in records if str(r.get("school_id", "")).strip().lower() != school_id
    ]
    if len(filtered) == len(records):
        return jsonify({"success": False, "message": "Member not found"}), 404

    save_db(db_key, filtered)
    return jsonify({"success": True})


@app.route("/api/cancel_reservation", methods=["POST"])
def api_cancel_reservation():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json or {}
    b_no = data.get("book_no")
    s_id = str(data.get("school_id", "")).strip().lower()
    request_id = str(data.get("request_id", "")).strip()
    books = get_db("books")
    transactions = get_db("transactions")

    def _cancel_status_allowed(tx):
        status = str(tx.get("status", "")).strip().lower()
        return status in {"", "reserved", "unavailable", "borrowed"}

    def _tx_book_ref(tx):
        return str(tx.get("book_no") or tx.get("book_id") or "").strip()

    def _parse_tx_date(tx):
        raw = str(tx.get("date") or tx.get("reserved_at") or "").strip()
        if not raw:
            return datetime.min
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return datetime.min

    candidates = [
        t
        for t in transactions
        if _tx_book_ref(t) == str(b_no or "").strip() and _cancel_status_allowed(t)
    ]

    target_transaction = None
    if request_id:
        target_transaction = next(
            (
                t
                for t in candidates
                if str(t.get("request_id", "")).strip() == request_id
            ),
            None,
        )
    if target_transaction is None and s_id:
        target_transaction = next(
            (
                t
                for t in candidates
                if str(t.get("school_id", "")).strip().lower() == s_id
            ),
            None,
        )
    if target_transaction is None and candidates:
        candidates.sort(key=_parse_tx_date, reverse=True)
        target_transaction = candidates[0]

    if target_transaction is None:
        return jsonify({"success": False, "message": "Active reservation not found"}), 404

    target_transaction["status"] = "Cancelled"
    target_transaction["cancelled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    for b in books:
        if b.get("book_no") == b_no and b.get("status") == "Reserved":
            b["status"] = "Available"

    save_db("transactions", transactions)
    save_db("books", books)
    return jsonify({"success": True})


@app.route("/api/process_transaction", methods=["POST"])
def api_process_trans():
    """
    MASTER TRANSACTION HANDLER
    Restored: Now handles 'borrow' logic for Kiosk/Tablet.
    """
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json or {}
    b_no = data.get("book_no")
    action = data.get("action")  # 'borrow' or 'return'
    s_id = str(data.get("school_id", "")).strip().lower()
    borrower_name = str(data.get("borrower_name") or "").strip()
    if not borrower_name:
        user = find_any_user(s_id)
        borrower_name = (user or {}).get("name") or s_id

    with _db_write_lock:
        books = get_db("books")
        transactions = get_db("transactions")
        normalized_book_no = str(b_no or "").strip()

        def _tx_book_ref(tx):
            return str(tx.get("book_no") or tx.get("book_id") or "").strip()

        # LOGIC 1: RETURN
        if action == "return":
            target_request_id = str(data.get("request_id", "")).strip()
            target_school_id = str(data.get("school_id", "")).strip().lower()
            matched_transaction = False
            normalize = lambda value: str(value or "").strip().lower()

            for b in books:
                if b.get("book_no") == b_no:
                    b["status"] = "Available"
            for t in transactions:
                tx_status = normalize(t.get("status"))
                if _tx_book_ref(t) != normalized_book_no or tx_status not in ["", "reserved", "borrowed", "unavailable"]:
                    continue

                tx_request_id = str(t.get("request_id", "")).strip()
                tx_school_id = str(t.get("school_id", "")).strip().lower()
                request_id_match = bool(target_request_id and tx_request_id and tx_request_id == target_request_id)
                school_id_match = bool(not target_request_id and target_school_id and tx_school_id == target_school_id)

                if target_request_id and not request_id_match:
                    continue
                if not target_request_id and target_school_id and not school_id_match:
                    continue

                if normalize(t.get("status")) == "borrowed":
                    matched_transaction = True

                t["status"] = "Returned"
                t["return_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

            approval_log = get_db("admin_approval_record")
            if not isinstance(approval_log, list):
                approval_log = []
            approval_changed = False
            for row in approval_log:
                if row.get("book_no") != b_no or normalize(row.get("status")) != "borrowed":
                    continue

                row_request_id = str(row.get("request_id", "")).strip()
                row_school_id = str(row.get("school_id", "")).strip().lower()
                request_id_match = bool(target_request_id and row_request_id and row_request_id == target_request_id)
                school_id_match = bool(not target_request_id and target_school_id and row_school_id == target_school_id)

                if target_request_id and not request_id_match:
                    continue
                if not target_request_id and target_school_id and not school_id_match:
                    continue

                row["status"] = "Returned"
                row["return_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                approval_changed = True

            if approval_changed:
                save_db("admin_approval_record", approval_log)

            # Always update book status regardless of transaction match
            save_db("books", books)
            save_db("transactions", transactions)
            return jsonify({"success": True, "matched": matched_transaction})

        # LOGIC 2: BORROW (Restored for Tablet)
        elif action == "borrow":
            target_book = next((b for b in books if b.get("book_no") == b_no), None)
            return_due_date = str(data.get("return_due_date", "")).strip()
            return_date_status = _get_date_restriction_status(return_due_date)
            if return_date_status.get("restricted"):
                reason = return_date_status.get("reason") or "Selected return date is restricted."
                return jsonify({"success": False, "message": reason}), 400

            reserved_candidates = [
                t for t in transactions if t.get("book_no") == b_no and t.get("status") == "Reserved"
            ]

            def _reservation_sort_key(tx):
                created_raw = str(tx.get("date") or "").strip()
                try:
                    created_dt = datetime.strptime(created_raw, "%Y-%m-%d %H:%M")
                except ValueError:
                    created_dt = datetime.max
                return _pickup_sort_key(tx), created_dt

            reserved_candidates.sort(key=_reservation_sort_key)
            reserved_transaction = reserved_candidates[0] if reserved_candidates else None

            if not s_id and reserved_transaction:
                s_id = str(reserved_transaction.get("school_id", "")).strip().lower()

            if s_id:
                selected = next(
                    (
                        tx
                        for tx in reserved_candidates
                        if str(tx.get("school_id", "")).strip().lower() == s_id
                    ),
                    None,
                )
                if selected:
                    reserved_transaction = selected

            pickup_schedule = str((reserved_transaction or {}).get("pickup_schedule", "")).strip()
            if pickup_schedule and return_due_date and return_due_date < pickup_schedule.split(" ")[0]:
                return jsonify({"success": False, "message": "You have picked backward! Pick a date forward!"}), 400

            can_borrow = target_book and target_book.get("status") != "Borrowed"

            if can_borrow and reserved_transaction:
                target_book["status"] = "Borrowed"
                chosen_school_id = str(reserved_transaction.get("school_id", "")).strip().lower()

                for t in transactions:
                    if t.get("book_no") == b_no and t.get("status") == "Reserved":
                        t_school_id = str(t.get("school_id", "")).strip().lower()
                        if t_school_id == chosen_school_id:
                            t["status"] = "Converted"
                        else:
                            pickup_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                            t["status"] = "Unavailable"
                            t["unavailable_reason"] = "This book was borrowed by another user before your reserved pickup date."
                            t["unavailable_at"] = pickup_at
                            t["pickup_at"] = pickup_at
                            t["borrowed_by"] = (reserved_transaction or {}).get("borrower_name", "") or borrower_name

                now = datetime.now()
                try:
                    parsed_due_date = datetime.strptime(return_due_date, "%Y-%m-%d") if return_due_date else (now + timedelta(days=2))
                except ValueError:
                    parsed_due_date = now + timedelta(days=2)

                approved_record = {
                    "book_no": b_no,
                    "title": (target_book or {}).get("title", ""),
                    "school_id": chosen_school_id,
                    "status": "Borrowed",
                    "date": now.strftime("%Y-%m-%d %H:%M"),
                    "expiry": parsed_due_date.strftime("%Y-%m-%d"),
                    "pickup_location": (reserved_transaction or {}).get("pickup_location", ""),
                    "pickup_schedule": (reserved_transaction or {}).get("pickup_schedule", ""),
                    "reservation_note": (reserved_transaction or {}).get("reservation_note", ""),
                    "borrower_name": (reserved_transaction or {}).get("borrower_name", "") or borrower_name,
                    "phone_number": (reserved_transaction or {}).get("phone_number", ""),
                    "reserved_at": (reserved_transaction or {}).get("date", ""),
                    "request_id": (reserved_transaction or {}).get("request_id")
                    or str(data.get("request_id", "")).strip()
                    or generate_request_id(),
                    "approved_by": str(data.get("approved_by", "")).strip() or "System Librarian",
                }
                transactions.append(approved_record)

                approval_log = get_db("admin_approval_record")
                if not isinstance(approval_log, list):
                    approval_log = []
                approval_log.append(approved_record)
                save_db("admin_approval_record", approval_log)
            else:
                return jsonify({"success": False, "message": "Book Unavailable"}), 400

        save_db("books", books)
        save_db("transactions", transactions)

    return jsonify({"success": True})


@app.route("/api/reserve", methods=["POST"])
def api_reserve():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json or {}
    b_no = data.get("book_no")
    s_id = str(data.get("school_id", "")).strip().lower()
    now = datetime.now()
    request_id = str(data.get("request_id", "")).strip() or generate_request_id()
    pickup_schedule = str(data.get("pickup_schedule", "")).strip()
    pickup_date = pickup_schedule.split(" ")[0] if pickup_schedule else ""
    borrower_name = str(data.get("borrower_name") or "").strip()
    if not borrower_name:
        user = find_any_user(s_id)
        borrower_name = (user or {}).get("name") or s_id

    pickup_date_status = _get_date_restriction_status(pickup_date)
    if pickup_date_status.get("restricted"):
        reason = pickup_date_status.get("reason") or "Selected pickup date is restricted."
        return jsonify({"success": False, "status": "error", "message": reason}), 400

    contact_type = str(data.get("contact_type", "")).strip().lower()
    contact_value = str(data.get("phone_number", "")).strip()
    if contact_type not in {"phone", "email"} or not contact_value:
        return jsonify({"success": False, "status": "error", "message": "Must fill the credentials!"}), 400
    if contact_type == "phone" and not re.fullmatch(r"\d{11}", contact_value):
        return jsonify({"success": False, "status": "error", "message": "Phone number must be exactly 11 numbers."}), 400
    if contact_type == "email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", contact_value):
        return jsonify({"success": False, "status": "error", "message": "Please provide a valid email address."}), 400

    with _db_write_lock:
        books = get_db("books")
        transactions = get_db("transactions")

        target_book = next((b for b in books if b.get("book_no") == b_no), None)
        if not target_book:
            return jsonify({"success": False, "status": "error", "message": "Book not found."}), 404

        if str(target_book.get("status", "")).strip().lower() == "borrowed":
            return jsonify({"success": False, "status": "error", "message": "This book is currently borrowed."}), 409

        active_reservations = [
            t
            for t in transactions
            if str(t.get("school_id", "")).strip().lower() == s_id
            and str(t.get("status", "")).strip().lower() in {"reserved", "borrowed"}
        ]

        if any(str(t.get("book_no", "")).strip() == str(b_no).strip() and str(t.get("status", "")).strip().lower() == "reserved" for t in active_reservations):
            return jsonify({"success": False, "status": "error", "message": "You already have an active reservation for this book."}), 400

        user_reserved_count = sum(1 for t in active_reservations if str(t.get("status", "")).strip().lower() == "reserved")
        if user_reserved_count >= 5:
            return jsonify({"success": False, "status": "error", "message": "Reservation limit reached (5 max)."}), 400

        if str(target_book.get("status", "")).strip().lower() == "available":
            target_book["status"] = "Reserved"

        reservation_payload = {
            "book_no": b_no,
            "title": target_book.get("title", ""),
            "school_id": s_id,
            "status": "Reserved",
            "date": now.strftime("%Y-%m-%d %H:%M"),
            "expiry": None,
            "borrower_name": borrower_name,
            "phone_number": contact_value,
            "contact_type": contact_type,
            "pickup_location": str(data.get("pickup_location", "")).strip(),
            "pickup_schedule": pickup_schedule,
            "reservation_note": str(data.get("reservation_note", "")).strip(),
            "request_id": request_id,
        }
        transactions.append(reservation_payload)

        save_db("books", books)
        save_db("transactions", transactions)

        reservation_log = get_db("reservation_transactions")
        if not isinstance(reservation_log, list):
            reservation_log = []
        reservation_log.append(reservation_payload)
        save_db("reservation_transactions", reservation_log)

    record_system_event("reserve", s_id)
    return jsonify({"success": True, "request_id": request_id})


@app.route("/api/monthly_activity_logs")
def api_monthly_activity_logs():
    return jsonify(_monthly_activity_summary())


from collections import Counter


def _parse_transaction_date(raw_date):
    value = str(raw_date or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _extract_transaction_date(tx):
    """Supports legacy and new date keys used by transaction records."""
    return _parse_transaction_date(tx.get("transaction_date") or tx.get("date"))


def _current_month_borrowed_transactions():
    now = datetime.now()
    valid_rows = []
    for tx in get_db("transactions"):
        tx_date = _extract_transaction_date(tx)
        if not tx_date:
            continue
        if tx_date.year == now.year and tx_date.month == now.month:
            if str(tx.get("status", "")).strip().lower() in {"borrowed", "returned"}:
                valid_rows.append(tx)
    return valid_rows


def _build_monthly_leaderboard_payload(limit=10):
    monthly_transactions = _current_month_borrowed_transactions()
    if not monthly_transactions:
        monthly_transactions = [
            tx
            for tx in get_db("transactions")
            if str(tx.get("status", "")).strip().lower() in {"borrowed", "returned"}
        ]
    books_map = {
        str(b.get("book_no", "")).strip().lower(): b for b in get_db("books")
    }
    profile_map = {}
    for user in get_db("users") + get_db("admins"):
        sid = str(user.get("school_id", "")).strip().lower()
        if sid and sid not in profile_map:
            profile_map[sid] = user

    borrower_counter = Counter()
    borrower_books = {}

    for tx in monthly_transactions:
        sid = str(tx.get("school_id", "")).strip()
        book_no = str(tx.get("book_no", "")).strip()
        if not sid or not book_no:
            continue

        borrower_counter[sid] += 1
        borrower_books.setdefault(sid, []).append(book_no)

    sorted_borrowers = sorted(
        borrower_counter.items(), key=lambda item: (-item[1], str(item[0]).lower())
    )[:limit]
    top_borrowers = []
    for idx, (sid, total) in enumerate(sorted_borrowers, start=1):
        profile = profile_map.get(str(sid).lower(), {})
        books_this_month = borrower_books.get(sid, [])
        favorite_book_no = ""
        favorite_book_title = "No records"
        if books_this_month:
            favorite_book_no, _ = Counter(books_this_month).most_common(1)[0]
            book_match = books_map.get(favorite_book_no.lower(), {})
            favorite_book_title = book_match.get("title") or favorite_book_no

        top_borrowers.append(
            {
                "rank": idx,
                "school_id": sid,
                "name": profile.get("name") or sid,
                "photo": profile.get("photo") or "default.png",
                "total_borrowed": total,
                "most_borrowed_book": f"{favorite_book_no} {favorite_book_title}".strip(),
            }
        )

    book_counter = Counter()
    for tx in monthly_transactions:
        book_no = str(tx.get("book_no", "")).strip()
        if book_no:
            book_counter[book_no] += 1

    sorted_books = sorted(
        book_counter.items(), key=lambda item: (-item[1], str(item[0]).lower())
    )[:limit]
    top_books = []
    for idx, (book_no, total) in enumerate(sorted_books, start=1):
        book = books_map.get(book_no.lower(), {})
        top_books.append(
            {
                "rank": idx,
                "book_no": book_no,
                "title": book.get("title") or book_no,
                "total_borrowed": total,
            }
        )

    return {"top_borrowers": top_borrowers, "top_books": top_books}


@app.route("/api/date_restrictions")
def api_date_restrictions():
    year = int(request.args.get("year", datetime.now().year))
    month = request.args.get("month")
    items = []

    if month:
        start = datetime(year, int(month), 1)
        end = start + timedelta(days=31)
        while end.month == start.month:
            end += timedelta(days=1)
    else:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)

    cursor = start
    while cursor < end:
        status = _get_date_restriction_status(cursor.strftime("%Y-%m-%d"))
        items.append(status)
        cursor += timedelta(days=1)

    return jsonify({"success": True, "items": items})


@app.route("/api/date_restrictions/set", methods=["POST"])
def api_set_date_restriction():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json or {}
    date_key = _normalize_date_only(data.get("date"))
    action = str(data.get("action", "")).strip().lower()
    reason = str(data.get("reason", "")).strip()
    if not date_key or action not in {"ban", "lift", "reset"}:
        return jsonify({"success": False, "message": "Invalid request"}), 400

    restrictions = _load_manual_date_restrictions()
    if action == "reset":
        restrictions.pop(date_key, None)
    else:
        restrictions[date_key] = {
            "action": action,
            "reason": reason,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    _save_manual_date_restrictions(restrictions)

    return jsonify({"success": True, "item": _get_date_restriction_status(date_key)})


@app.route("/api/date_restrictions/check")
def api_check_date_restriction():
    date_key = _normalize_date_only(request.args.get("date"))
    if not date_key:
        return jsonify({"success": False, "message": "date is required"}), 400
    status = _get_date_restriction_status(date_key)
    return jsonify({"success": True, **status})


def _is_staff_session_valid():
    """Checks active staff session for protected leaderboard APIs."""
    staff_id = (
        str(request.headers.get("X-School-Id", request.args.get("school_id", "")))
        .strip()
        .lower()
    )
    token = str(
        request.headers.get("X-Session-Token", request.args.get("token", ""))
    ).strip()
    if not staff_id or not is_session_valid(staff_id, token):
        return False
    user = find_any_user(staff_id)
    return bool(user and user.get("is_staff"))


@app.route("/api/leaderboard/top-borrowers")
def api_leaderboard_top_borrowers():
    """Top 10 borrowers for the current month (public endpoint)."""
    payload = _build_monthly_leaderboard_payload(limit=10)
    return jsonify(
        [
            {
                "school_id": row["school_id"],
                "total": row["total_borrowed"],
                "name": row["name"],
                "photo": row["photo"],
            }
            for row in payload["top_borrowers"]
        ]
    )


@app.route("/api/leaderboard/top-books")
def api_leaderboard_top_books():
    """Top 10 books for the current month (staff only endpoint)."""
    if not _is_staff_session_valid():
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    payload = _build_monthly_leaderboard_payload(limit=10)
    return jsonify(
        [
            {"book_no": row["book_no"], "total": row["total_borrowed"]}
            for row in payload["top_books"]
        ]
    )


@app.route("/api/monthly_leaderboard")
def api_monthly_leaderboard():
    return jsonify(_build_monthly_leaderboard_payload(limit=10))


@app.route("/api/leaderboard_profile/<school_id>")
def api_leaderboard_profile(school_id):
    lookup_id = str(school_id or "").strip()
    if not lookup_id:
        return jsonify({"success": False, "message": "Missing school_id"}), 400

    leaderboard = _build_monthly_leaderboard_payload(limit=1000)
    match = next(
        (
            row
            for row in leaderboard["top_borrowers"]
            if str(row.get("school_id", "")).lower() == lookup_id.lower()
        ),
        None,
    )

    if not match:
        user = find_any_user(lookup_id)
        if not user:
            return jsonify({"success": False, "message": "Profile not found"}), 404
        match = {
            "school_id": user.get("school_id") or lookup_id,
            "name": user.get("name") or lookup_id,
            "photo": user.get("photo") or "default.png",
            "total_borrowed": 0,
            "most_borrowed_book": "No records",
        }

    return jsonify({"success": True, "profile": match})


def _normalize_home_cards(raw_cards):
    normalized = []
    source = raw_cards if isinstance(raw_cards, list) else []
    for card_id in range(1, 5):
        existing = next(
            (
                row
                for row in source
                if isinstance(row, dict) and int(row.get("id", 0) or 0) == card_id
            ),
            {},
        )
        normalized.append(
            {
                "id": card_id,
                "title": str(existing.get("title", "")).strip(),
                "body": str(existing.get("body", "")).strip(),
            }
        )
    return normalized


def _normalize_news_posts(raw_posts):
    if not isinstance(raw_posts, list):
        return []

    normalized = []
    for row in raw_posts:
        if not isinstance(row, dict):
            continue
        post_id = str(row.get("id", "")).strip() or uuid.uuid4().hex
        image_name = row.get("image_filename")
        if image_name is None:
            final_image = None
        else:
            image_clean = str(image_name).strip()
            final_image = image_clean if image_clean else None

        normalized.append(
            {
                "id": post_id,
                "title": str(row.get("title", "")).strip(),
                "summary": str(row.get("summary", "")).strip(),
                "body": str(row.get("body", "")).strip(),
                "image_filename": final_image,
                "date": str(row.get("date", "")).strip() or datetime.now().strftime("%Y-%m-%d %H:%M"),
                "author": str(row.get("author", "")).strip() or "Admin",
            }
        )
    return normalized


@app.route("/api/home_cards")
def api_get_home_cards():
    cards = _normalize_home_cards(get_db("home_cards"))
    if get_db("home_cards") != cards:
        save_db("home_cards", cards)
    return jsonify(cards)


@app.route("/api/home_cards", methods=["POST"])
def api_save_home_cards():
    if not require_admin_session():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    candidate = payload.get("cards") if isinstance(payload, dict) and isinstance(payload.get("cards"), list) else payload
    if not isinstance(candidate, list):
        return jsonify({"success": False, "message": "Cards payload must be a list."}), 400

    source_by_id = {}
    for row in candidate:
        if not isinstance(row, dict):
            continue
        try:
            row_id = int(row.get("id", 0))
        except Exception:
            continue
        if 1 <= row_id <= 4:
            source_by_id[row_id] = row

    final_cards = []
    for card_id in range(1, 5):
        row = source_by_id.get(card_id, {})
        final_cards.append(
            {
                "id": card_id,
                "title": str(row.get("title", "")).strip(),
                "body": str(row.get("body", "")).strip(),
            }
        )

    save_db("home_cards", final_cards)
    return jsonify({"success": True, "cards": final_cards})


@app.route("/api/news_posts")
def api_get_news_posts():
    posts = _normalize_news_posts(get_db("news_posts"))
    posts.sort(key=lambda row: row.get("date", ""), reverse=True)
    if get_db("news_posts") != posts:
        save_db("news_posts", posts)
    return jsonify(posts)


@app.route("/api/news_posts", methods=["POST"])
def api_create_news_post():
    admin_id = require_admin_session()
    if not admin_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    title = str(request.form.get("title", "")).strip()
    summary = str(request.form.get("summary", "")).strip()
    body = str(request.form.get("body", "")).strip()
    if not title or not summary or not body:
        return jsonify({"success": False, "message": "Title, summary, and body are required."}), 400

    image_filename = save_post_image(request.files.get("image"))
    if request.files.get("image") and not image_filename:
        return jsonify({"success": False, "message": "Unsupported file type."}), 400

    admin_profile = find_any_user(admin_id) or {}
    new_post = {
        "id": uuid.uuid4().hex,
        "title": title,
        "summary": summary,
        "body": body,
        "image_filename": image_filename,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "author": str(admin_profile.get("name") or "Admin").strip(),
    }

    posts = _normalize_news_posts(get_db("news_posts"))
    posts.insert(0, new_post)
    save_db("news_posts", posts)
    return jsonify({"success": True, "post": new_post, "posts": posts})


@app.route("/api/news_posts/<post_id>", methods=["DELETE"])
def api_delete_news_post(post_id):
    if not require_admin_session():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    lookup = str(post_id or "").strip().lower()
    posts = _normalize_news_posts(get_db("news_posts"))
    idx = next((i for i, row in enumerate(posts) if str(row.get("id", "")).strip().lower() == lookup), -1)
    if idx < 0:
        return jsonify({"success": False, "message": "Post not found"}), 404

    deleted_post = posts.pop(idx)
    image_name = deleted_post.get("image_filename")
    if image_name:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_name)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                logger.warning(f"Unable to remove deleted post media: {image_path}")

    save_db("news_posts", posts)
    return jsonify({"success": True, "posts": posts})


@app.route("/Profile/<path:filename>")
def serve_file(filename):
    target = os.path.join(PROFILE_FOLDER, filename)
    default = os.path.join(PROFILE_FOLDER, "default.png")

    if os.path.isfile(target):
        return send_from_directory(PROFILE_FOLDER, filename)
    elif os.path.isfile(default):
        return send_from_directory(PROFILE_FOLDER, "default.png")
    else:
        import base64
        from flask import Response

        blank = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
            "HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAA"
            "SUVORK5CYII="
        )
        return Response(blank, mimetype="image/png")


if __name__ == "__main__":
    initialize_system()
    app.run(host="0.0.0.0", port=5000, debug=False)
