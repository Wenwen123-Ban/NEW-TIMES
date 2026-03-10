from django.http import JsonResponse
from core.models import UserProfile
from .utils import list_response


def users_list(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    return list_response(UserProfile.objects.all().order_by('school_id'))
