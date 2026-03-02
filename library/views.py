import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import ReservationTransaction


@require_POST
def reserve(request):
    data = json.loads(request.body or '{}')
    try:
        ReservationTransaction.reserve_book(
            book_no=data.get('book_no'),
            school_id=data.get('school_id'),
            borrower_name=data.get('borrower_name', ''),
            pickup_location=data.get('pickup_location', ''),
            pickup_schedule=data.get('pickup_schedule', ''),
            reservation_note=data.get('reservation_note', ''),
        )
        return JsonResponse({'success': True})
    except ValidationError as exc:
        return JsonResponse({'success': False, 'status': 'error', 'message': exc.messages[0]}, status=400)


@require_POST
def cancel_reservation(request):
    data = json.loads(request.body or '{}')
    success = ReservationTransaction.cancel_reservation(
        book_no=data.get('book_no'),
        school_id=data.get('school_id'),
    )
    if not success:
        return JsonResponse({'success': False, 'message': 'Active reservation not found'}, status=404)
    return JsonResponse({'success': True})
