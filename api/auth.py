from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import UserProfile
from .utils import parse_json_body


@csrf_exempt
def login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    payload = parse_json_body(request)
    school_id = str(payload.get('school_id', '')).strip()
    password = str(payload.get('password', '')).strip()
    user = UserProfile.objects.filter(school_id=school_id, password=password).first()
    if not user:
        return JsonResponse({'ok': False, 'message': 'Invalid credentials'}, status=401)
    return JsonResponse({'ok': True, 'school_id': user.school_id, 'name': user.name, 'category': user.category})
