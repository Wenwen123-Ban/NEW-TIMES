import json
import os
import re
import uuid
from datetime import datetime, timedelta

from flask import jsonify, request
from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def _db_path(app, filename):
    return os.path.join(app.root_path, filename)


def _read_json(app, filename, fallback):
    path = _db_path(app, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return fallback


def _write_json(app, filename, data):
    path = _db_path(app, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def register_auth_routes(app, find_any_user, active_sessions, session_timeout_hours, save_sessions_fn=None):
    @app.route('/api/verify_id', methods=['POST'])
    def api_verify_id():
        data = request.json or {}
        school_id = str(data.get('school_id', '')).strip().lower()
        if not school_id:
            return jsonify({'success': False, 'message': 'School ID is required.'}), 400

        user = find_any_user(school_id)
        if not user:
            return jsonify({'success': False, 'message': 'School ID not found.'}), 404

        if user.get('is_staff', False):
            return jsonify({
                'success': False,
                'message': 'Admin accounts must log in with password via Admin Login.'
            }), 403

        status = str(user.get('status', 'active')).strip().lower()
        if status == 'pending':
            return jsonify({
                'success': False,
                'status': 'pending',
                'message': 'Account pending approval.'
            }), 403
        if status == 'rejected':
            return jsonify({
                'success': False,
                'status': 'rejected',
                'message': 'Registration was not approved.'
            }), 403

        token = f"{school_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        active_sessions[school_id] = {
            'token': token,
            'expires': datetime.now() + timedelta(hours=session_timeout_hours),
        }
        if save_sessions_fn:
            save_sessions_fn()

        profile = {
            'name': user.get('name', school_id),
            'school_id': school_id,
            'is_staff': bool(user.get('is_staff', False)),
            'phone_number': user.get('phone_number', ''),
            'photo': user.get('photo', 'default.png'),
            'source': user.get('source', 'users'),
        }
        return jsonify({'success': True, 'token': token, 'profile': profile})

    @app.route('/api/register_request', methods=['POST'], endpoint='api_register_request_formdata')
    def api_register_request_formdata():
        name = str(request.form.get('name', '')).strip()
        school_id = str(request.form.get('school_id', '')).strip().lower()
        email = str(request.form.get('email', '')).strip().lower()
        password = str(request.form.get('password', '')).strip()

        if not all([name, school_id, email, password]):
            return jsonify({'success': False, 'message': 'All fields are required.'}), 400
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'success': False, 'message': 'Invalid email address.'}), 400
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

        users = _read_json(app, 'users.json', [])
        if any(str(u.get('school_id', '')).strip().lower() == school_id for u in users):
            return jsonify({'success': False, 'message': 'This School ID is already registered. Please log in.'}), 409

        admins = _read_json(app, 'admins.json', [])
        if any(str(a.get('school_id', '')).strip().lower() == school_id for a in admins):
            return jsonify({'success': False, 'message': 'This ID belongs to a staff account.'}), 409

        requests = _read_json(app, 'registration_requests.json', [])
        if any(str(r.get('school_id', '')).strip().lower() == school_id and str(r.get('status', '')).lower() == 'pending' for r in requests):
            return jsonify({'success': False, 'status': 'pending', 'message': 'A pending request for this ID already exists.'}), 409

        photo_filename = 'default.png'
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            ext = os.path.splitext(secure_filename(photo_file.filename))[1].lower() or '.jpg'
            if ext in ALLOWED_IMAGE_EXTENSIONS:
                timestamp = int(datetime.now().timestamp() * 1000)
                photo_filename = f'{school_id}_{timestamp}{ext}'
                profile_folder = os.path.join(app.root_path, 'Profile')
                os.makedirs(profile_folder, exist_ok=True)
                photo_file.save(os.path.join(profile_folder, photo_filename))

        new_req = {
            'request_id': str(uuid.uuid4()),
            'school_id': school_id,
            'name': name,
            'email': email,
            'password': password,
            'photo': photo_filename,
            'status': 'pending',
            'date_created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reviewed_by': '',
            'reviewed_at': '',
        }

        requests.append(new_req)
        _write_json(app, 'registration_requests.json', requests)

        return jsonify({'success': True, 'message': 'Registration request submitted.', 'request_id': new_req['request_id']}), 200
