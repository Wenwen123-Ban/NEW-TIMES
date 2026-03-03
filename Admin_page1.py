import os
import json
import uuid
import logging
import sys
import operator
import random  # REQUIRED for Ticket Codes
import string  # REQUIRED for Ticket Codes
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    redirect,
    url_for,
    make_response,
)
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("LBAS_Command_Center")

PROFILE_FOLDER = "Profile"
CREATORS_PROFILE_DB = "creators_profiles.json"
app.config["UPLOAD_FOLDER"] = PROFILE_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

if not os.path.exists(PROFILE_FOLDER):
    os.makedirs(PROFILE_FOLDER)
    logger.info(f"SYSTEM INIT: Created secure profile storage at ./{PROFILE_FOLDER}")

# Database Map: Full restoration of all required DBs
DB_FILES = {
    "books": "books.json",
    "admins": "admins.json",
    "users": "users.json",
    "transactions": "transactions.json",
    "ratings": "ratings.json",
    "config": "system_config.json",
    "tickets": "tickets.json",  # Password Recovery Registry
    "categories": "categories.json",
    "date_restricted": "Date_Restricted.json",
    "reservation_transactions": "reservation_transaction.json",
    "admin_approval_record": "Admin_approval_record.json",
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


def initialize_system():
    logger.info("SYSTEM INIT: verifying database integrity...")
    ensure_creators_profile_db()
    for key, file_path in DB_FILES.items():
        if not os.path.exists(file_path):
            if key == "config":
                initial_data = {
                    "system_version": "7.2 Beta",
                    "rating_enabled": True,
                    "last_reboot": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            elif key == "categories":
                initial_data = ["General", "Mathematics", "Science", "Literature"]
            elif key == "date_restricted":
                initial_data = {}
            else:
                initial_data = []
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=4)

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
                "status": "approved",
                "created_at": "SYSTEM_INIT",
            }
        )
        save_db("admins", admins)


def get_db(key):
    try:
        if not os.path.exists(DB_FILES[key]):
            return {} if key == "config" else []
        with open(DB_FILES[key], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"DB READ ERROR ({key}): {e}")
        return {} if key == "config" else []


def save_db(key, data):
    try:
        with open(DB_FILES[key], "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"DB WRITE ERROR ({key}): {e}")


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
            admin["registry_origin"] = "admins.json"
            admin["is_staff"] = True
            return admin

    for student in get_db("users"):
        if str(student.get("school_id", "")).strip().lower() == s_id:
            student["registry_origin"] = "users.json"
            student["is_staff"] = False
            return student
    return None


def is_mobile_request():
    ua = request.headers.get("User-Agent", "").lower()
    return any(
        x in ua for x in ["mobile", "android", "iphone", "ipad", "windows phone"]
    )


def run_auto_sync_engine():
    """
    CRITICAL SYNC ENGINE (RESTORED):
    1. Manages Book Reservations (Expires them after 30 mins).
    2. Manages Ticket Requests (Deletes them after 5 mins).
    3. Manages Overdue Calculations.
    """
    books = get_db("books")
    transactions = get_db("transactions")
    tickets = get_db("tickets")
    now = datetime.now()
    changes_made = False

    # 1. Sync Reservations (legacy expiry support only)
    for t in transactions:
        if t["status"] == "Reserved" and "expiry" in t and t.get("expiry"):
            try:
                if now > datetime.strptime(t["expiry"], "%Y-%m-%d %H:%M"):
                    t["status"] = "Expired"
                    for b in books:
                        if b["book_no"] == t["book_no"]:
                            b["status"] = "Available"
                            changes_made = True
            except:
                pass

    # 2. Sync Recovery Tickets (Cleanup expired)
    initial_tickets = len(tickets)
    tickets = [
        t for t in tickets if datetime.strptime(t["expiry"], "%Y-%m-%d %H:%M:%S") > now
    ]
    if len(tickets) != initial_tickets:
        save_db("tickets", tickets)

    if changes_made:
        save_db("books", books)
        save_db("transactions", transactions)

    return books


@app.route("/")
def index_gateway():
    if is_mobile_request():
        return redirect(url_for("lbas_site"))
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
    return redirect(url_for("index_gateway"))




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
        return jsonify({"success": False, "message": "ID not found"}), 404

    if user["status"] == "pending":
        return jsonify({"success": False, "message": "Account Pending Approval"}), 401

    if id_only and not user.get("is_staff", False):
        token = str(uuid.uuid4())
        ACTIVE_SESSIONS[s_id] = {
            "token": token,
            "expires": datetime.now() + timedelta(hours=SESSION_TIMEOUT_HOURS),
        }
        return jsonify({"success": True, "token": token, "profile": user})

    if user.get("password") == pwd:
        token = str(uuid.uuid4())
        ACTIVE_SESSIONS[s_id] = {
            "token": token,
            "expires": datetime.now() + timedelta(hours=SESSION_TIMEOUT_HOURS),
        }
        return jsonify({"success": True, "token": token, "profile": user})

    return jsonify({"success": False, "message": "Invalid Password"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    token = request.headers.get("Authorization")
    for user_id, session in list(ACTIVE_SESSIONS.items()):
        if isinstance(session, dict) and session.get("token") == token:
            del ACTIVE_SESSIONS[user_id]
            return jsonify({"success": True})
    return jsonify({"success": False}), 401


@app.route("/api/books")
def api_get_books():
    if not require_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify(run_auto_sync_engine())


@app.route("/api/categories")
def api_get_categories():
    return jsonify(sync_categories_with_books())


@app.route("/api/categories", methods=["POST"])
def api_add_category():
    category = sanitize_category_name(request.json.get("category"))
    if not category:
        return jsonify({"success": False, "message": "Invalid category name"}), 400

    categories = get_categories()
    if category in categories:
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
    return jsonify(get_db("transactions"))


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
    books = get_db("books")
    transactions = get_db("transactions")

    changed = False
    for t in transactions:
        if (
            t.get("book_no") == b_no
            and str(t.get("school_id", "")).strip().lower() == s_id
            and t.get("status") in ["Reserved", "Unavailable"]
        ):
            t["status"] = "Cancelled"
            t["cancelled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            changed = True

    if not changed:
        return jsonify({"success": False, "message": "Active reservation not found"}), 404

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
    data = request.json
    b_no = data.get("book_no")
    action = data.get("action")  # 'borrow' or 'return'
    s_id = str(data.get("school_id", "")).strip().lower()

    books = get_db("books")
    transactions = get_db("transactions")

    # LOGIC 1: RETURN
    if action == "return":
        for b in books:
            if b["book_no"] == b_no:
                b["status"] = "Available"
        # Close all open transactions for this book
        for t in transactions:
            if t["book_no"] == b_no and t["status"] in ["Reserved", "Borrowed"]:
                t["status"] = "Returned"
                t["return_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # LOGIC 2: BORROW (Restored for Tablet)
    elif action == "borrow":
        target_book = next((b for b in books if b["book_no"] == b_no), None)
        return_due_date = str(data.get("return_due_date", "")).strip()
        return_date_status = _get_date_restriction_status(return_due_date)
        if return_date_status.get("restricted"):
            reason = return_date_status.get("reason") or "Selected return date is restricted."
            return jsonify({"success": False, "message": reason}), 400

        # Resolve active reservation first so librarian approvals can convert reservations
        # even if the request does not include school_id.
        reserved_candidates = [
            t for t in transactions if t.get("book_no") == b_no and t.get("status") == "Reserved"
        ]

        def _reservation_sort_key(tx):
            pickup = str(tx.get("pickup_schedule") or "").strip()
            try:
                pickup_dt = datetime.strptime(pickup, "%Y-%m-%d")
            except ValueError:
                pickup_dt = datetime.max
            created_raw = str(tx.get("date") or "").strip()
            try:
                created_dt = datetime.strptime(created_raw, "%Y-%m-%d %H:%M")
            except ValueError:
                created_dt = datetime.max
            return pickup_dt, created_dt

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

        can_borrow = target_book and target_book.get("status") != "Borrowed"

        if can_borrow and reserved_transaction:
            target_book["status"] = "Borrowed"

            chosen_school_id = str(reserved_transaction.get("school_id", "")).strip().lower()

            # Close queue: chosen reservation is converted, all other queued reservations are marked unavailable.
            for t in transactions:
                if t["book_no"] == b_no and t["status"] == "Reserved":
                    t_school_id = str(t.get("school_id", "")).strip().lower()
                    if t_school_id == chosen_school_id:
                        t["status"] = "Converted"
                    else:
                        t["status"] = "Unavailable"
                        t["unavailable_reason"] = "This book was borrowed by another user before your reserved pickup date."
                        t["unavailable_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

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
                "borrower_name": (reserved_transaction or {}).get("borrower_name", ""),
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
    data = request.json
    b_no = data.get("book_no")
    s_id = str(data.get("school_id", "")).strip().lower()

    books = get_db("books")
    transactions = get_db("transactions")
    now = datetime.now()
    request_id = str(data.get("request_id", "")).strip() or generate_request_id()
    pickup_schedule = str(data.get("pickup_schedule", "")).strip()
    pickup_date_status = _get_date_restriction_status(pickup_schedule)
    if pickup_date_status.get("restricted"):
        reason = pickup_date_status.get("reason") or "Selected pickup date is restricted."
        return jsonify({"success": False, "status": "error", "message": reason}), 400

    # 1) Cleanup expired reservations for this user before any validation.
    expired_found = False
    for t in transactions:
        if t.get("school_id") != s_id or t.get("status") != "Reserved":
            continue
        expiry_raw = t.get("expiry")
        if not expiry_raw:
            continue
        try:
            if now > datetime.strptime(expiry_raw, "%Y-%m-%d %H:%M"):
                t["status"] = "Expired"
                expired_found = True
                for b in books:
                    if b.get("book_no") == t.get("book_no") and b.get("status") == "Reserved":
                        b["status"] = "Available"
                        break
        except ValueError:
            continue

    # 2) Query active reservations after cleanup.
    active_reservations = [
        t
        for t in transactions
        if t.get("school_id") == s_id and t.get("status") == "Reserved"
    ]

    # 3) Block duplicate active reservation for same book.
    if any(t.get("book_no") == b_no for t in active_reservations):
        if expired_found:
            save_db("books", books)
            save_db("transactions", transactions)
        return (
            jsonify(
                {
                    "success": False,
                    "status": "error",
                    "message": "You already have an active reservation for this book.",
                }
            ),
            400,
        )

    # 4) Enforce max active reservation count.
    if len(active_reservations) >= 5:
        if expired_found:
            save_db("books", books)
            save_db("transactions", transactions)
        return (
            jsonify(
                {
                    "success": False,
                    "status": "error",
                    "message": "Reservation limit reached (5 max).",
                }
            ),
            400,
        )

    for b in books:
        if b["book_no"] == b_no and b["status"] != "Borrowed":
            reservation_payload = {
                    "book_no": b_no,
                    "title": b.get("title", ""),
                    "school_id": s_id,
                    "status": "Reserved",
                    "date": now.strftime("%Y-%m-%d %H:%M"),
                    "expiry": None,
                    "borrower_name": str(data.get("borrower_name", "")).strip(),
                    "phone_number": str(data.get("phone_number", "")).strip(),
                    "pickup_location": str(data.get("pickup_location", "")).strip(),
                    "pickup_schedule": pickup_schedule,
                    "reservation_note": str(data.get("reservation_note", "")).strip(),
                    "request_id": request_id,
                }
            transactions.append(reservation_payload)
            save_db("transactions", transactions)

            reservation_log = get_db("reservation_transactions")
            if not isinstance(reservation_log, list):
                reservation_log = []
            reservation_log.append(reservation_payload)
            save_db("reservation_transactions", reservation_log)
            return jsonify({"success": True, "request_id": request_id})

    if expired_found:
        save_db("books", books)
        save_db("transactions", transactions)

    return jsonify({"success": False, "message": "Unavailable"})




@app.route("/api/toggle_rating", methods=["POST"])
def api_toggle_rating():
    """Global switch to enable/disable the rating prompt on Tablet/LBAS."""
    config = get_db("config")
    current = config.get("rating_enabled", False)
    config["rating_enabled"] = not current
    config["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_db("config", config)
    return jsonify({"success": True, "new_state": config["rating_enabled"]})


@app.route("/api/rating_status/<school_id>")
def api_rating_eligibility(school_id):
    """Checks if a user has already rated to prevent spam."""
    config = get_db("config")
    if not config.get("rating_enabled", False):
        return jsonify({"show": False, "reason": "System Closed"})

    ratings = get_db("ratings")
    search_id = str(school_id).strip().lower()
    already_done = any(
        str(r.get("school_id")).strip().lower() == search_id for r in ratings
    )
    return jsonify({"show": not already_done})


@app.route("/api/rate", methods=["POST"])
def api_submit_rating():
    """Saves student feedback with session token validation."""
    data = request.json
    s_id = str(data.get("school_id", "")).strip().lower()

    if not is_session_valid(s_id, data.get("token")):
        return jsonify({"success": False, "message": "Security Handshake Failed"}), 401

    ratings = get_db("ratings")
    ratings.append(
        {
            "rating_id": str(uuid.uuid4())[:10],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "school_id": s_id,
            "stars": int(data.get("stars", 5)),
            "feedback": data.get("feedback", "N/A"),
            "platform": "Mobile" if is_mobile_request() else "Tablet",
        }
    )
    save_db("ratings", ratings)
    return jsonify({"success": True})


@app.route("/api/ratings_summary")
def api_get_ratings():
    """Data feed for the Developer Analysis dashboard."""
    return jsonify(get_db("ratings"))


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


@app.route("/Profile/<path:filename>")
def serve_file(filename):
    try:
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
    except:
        return send_from_directory(app.config["UPLOAD_FOLDER"], "default.png")


if __name__ == "__main__":
    initialize_system()
    app.run(host="127.0.0.1", port=5000, debug=False)
