from __future__ import annotations

import json
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.contrib.auth.hashers import check_password, make_password

from .services.json_store import read_json, write_json, now_str


@ensure_csrf_cookie
@require_GET
def reserve_page(request):
    return render(request, 'LBAS.html')


@ensure_csrf_cookie
@require_GET
def admin_dashboard_page(request):
    return render(request, 'admin_dashboard.html')


@require_POST
@csrf_exempt
def api_login(request):
    payload = json.loads(request.body or '{}')
    school_id = str(payload.get('school_id', '')).strip()
    password = str(payload.get('password', '')).strip()

    users = read_json('users')
    admins = read_json('admins')
    for row in users + admins:
        if str(row.get('school_id', '')).strip().lower() != school_id.lower():
            continue
        saved = str(row.get('password', ''))
        valid = saved == password
        if saved.startswith('pbkdf2_'):
            valid = check_password(password, saved)
        if not valid:
            return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=401)
        return JsonResponse({'success': True, 'user': row, 'token': f'token-{school_id}'})
    return JsonResponse({'success': False, 'message': 'User not found'}, status=404)


@require_GET
def api_books(request):
    return JsonResponse(read_json('books'), safe=False)


@require_GET
def api_users(request):
    return JsonResponse(read_json('users'), safe=False)


@require_GET
def api_admins(request):
    return JsonResponse(read_json('admins'), safe=False)


@require_GET
def api_transactions(request):
    return JsonResponse(read_json('transactions'), safe=False)


@require_GET
def api_categories(request):
    return JsonResponse(read_json('categories'), safe=False)


@require_GET
def api_user_detail(request, s_id: str):
    s_id = s_id.strip().lower()
    users = read_json('users') + read_json('admins')
    for user in users:
        if str(user.get('school_id', '')).strip().lower() == s_id:
            return JsonResponse(user)
    return JsonResponse({'message': 'Not found'}, status=404)


def _blocked_dates_set() -> set[str]:
    blocked = read_json('blocked_dates')
    return {str(item.get('date')) for item in blocked if isinstance(item, dict) and item.get('date')}


@require_POST
@csrf_exempt
def api_reserve(request):
    payload = json.loads(request.body or '{}')
    school_id = str(payload.get('school_id', '')).strip()
    book_no = str(payload.get('book_no', '')).strip()
    pickup_date = str(payload.get('pickup_date', '')).strip()

    if not school_id or not book_no or not pickup_date:
        return JsonResponse({'success': False, 'message': 'school_id, book_no, pickup_date required'}, status=400)

    try:
        pickup_dt = datetime.strptime(pickup_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'pickup_date must be YYYY-MM-DD'}, status=400)

    if pickup_dt.weekday() >= 5:
        return JsonResponse({'success': False, 'message': 'Weekend reservations are blocked'}, status=400)

    if pickup_date in _blocked_dates_set():
        return JsonResponse({'success': False, 'message': 'Selected date is blocked'}, status=400)

    tx = read_json('transactions')
    sid = school_id.lower()
    pending = [t for t in tx if str(t.get('school_id', '')).lower() == sid and str(t.get('status', '')).upper() in {'PENDING', 'RESERVED'}]
    approved = [t for t in tx if str(t.get('school_id', '')).lower() == sid and str(t.get('status', '')).upper() in {'APPROVED', 'BORROWED'}]
    duplicate = [t for t in tx if str(t.get('school_id', '')).lower() == sid and str(t.get('book_no', '')) == book_no and str(t.get('status', '')).upper() in {'PENDING', 'RESERVED', 'APPROVED', 'BORROWED'}]

    if len(pending) >= 3:
        return JsonResponse({'success': False, 'message': 'Max 3 pending reservations'}, status=400)
    if len(approved) >= 3:
        return JsonResponse({'success': False, 'message': 'Max 3 approved borrows'}, status=400)
    if duplicate:
        return JsonResponse({'success': False, 'message': 'Duplicate reservation is not allowed'}, status=400)

    tx.append({
        'book_no': book_no,
        'school_id': school_id,
        'pickup_date': pickup_date,
        'date': now_str(),
        'status': 'PENDING',
    })
    write_json('transactions', tx)
    return JsonResponse({'success': True, 'message': 'Reservation created (PENDING)'})


@require_POST
@csrf_exempt
def api_cancel_reservation(request):
    payload = json.loads(request.body or '{}')
    school_id = str(payload.get('school_id', '')).strip().lower()
    book_no = str(payload.get('book_no', '')).strip()

    tx = read_json('transactions')
    for row in tx:
        if str(row.get('school_id', '')).strip().lower() == school_id and str(row.get('book_no', '')) == book_no and str(row.get('status', '')).upper() in {'PENDING', 'RESERVED'}:
            row['status'] = 'CANCELLED'
    write_json('transactions', tx)
    return JsonResponse({'success': True})


@require_POST
@csrf_exempt
def api_approve_reservation(request):
    payload = json.loads(request.body or '{}')
    school_id = str(payload.get('school_id', '')).strip().lower()
    book_no = str(payload.get('book_no', '')).strip()
    approved_by = str(payload.get('approved_by', 'admin')).strip()

    tx = read_json('transactions')
    for row in tx:
        if str(row.get('school_id', '')).strip().lower() == school_id and str(row.get('book_no', '')) == book_no and str(row.get('status', '')).upper() in {'PENDING', 'RESERVED'}:
            row['status'] = 'APPROVED'
            row['approved_by'] = approved_by
            row['approved_at'] = now_str()
            write_json('transactions', tx)
            return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'message': 'Reservation not found'}, status=404)


@require_POST
@csrf_exempt
def api_add_blocked_date(request):
    payload = json.loads(request.body or '{}')
    date = str(payload.get('date', '')).strip()
    reason = str(payload.get('reason', '')).strip() or 'Unavailable'
    if not date:
        return JsonResponse({'success': False, 'message': 'date required'}, status=400)

    blocked = read_json('blocked_dates')
    if not any(str(item.get('date')) == date for item in blocked if isinstance(item, dict)):
        blocked.append({'date': date, 'reason': reason, 'created_at': now_str()})
        write_json('blocked_dates', blocked)
    return JsonResponse({'success': True})


@require_POST
@csrf_exempt
def api_remove_blocked_date(request):
    payload = json.loads(request.body or '{}')
    date = str(payload.get('date', '')).strip()
    blocked = read_json('blocked_dates')
    blocked = [item for item in blocked if str(item.get('date')) != date]
    write_json('blocked_dates', blocked)
    return JsonResponse({'success': True})


@require_POST
@csrf_exempt
def api_hash_admin_passwords(request):
    admins = read_json('admins')
    for row in admins:
        password = str(row.get('password', ''))
        if password and not password.startswith('pbkdf2_'):
            row['password'] = make_password(password)
    write_json('admins', admins)
    return JsonResponse({'success': True})
