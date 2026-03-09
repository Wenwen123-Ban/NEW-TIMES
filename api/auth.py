from datetime import datetime, timedelta
from flask import request, jsonify


def register_auth_routes(app, find_any_user, active_sessions, session_timeout_hours):
    @app.route('/api/verify_id', methods=['POST'])
    def api_verify_id():
        data = request.json or {}
        school_id = str(data.get('school_id', '')).strip().lower()
        if not school_id:
            return jsonify({'success': False, 'message': 'School ID is required.'}), 400

        user = find_any_user(school_id)
        if not user:
            return jsonify({'success': False, 'message': 'School ID not found.'}), 404

        token = f"{school_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        active_sessions[school_id] = {
            'token': token,
            'expires': datetime.now() + timedelta(hours=session_timeout_hours),
        }

        profile = {
            'name': user.get('name', school_id),
            'school_id': school_id,
            'is_staff': bool(user.get('is_staff', False)),
            'phone_number': user.get('phone_number', ''),
            'photo': user.get('photo', 'default.png'),
            'source': user.get('source', 'users'),
        }
        return jsonify({'success': True, 'token': token, 'profile': profile})
