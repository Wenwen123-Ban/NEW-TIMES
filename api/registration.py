from django.http import JsonResponse
from core.models import RegistrationRequest
from .utils import list_response


def registration_requests(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    return list_response(RegistrationRequest.objects.all().order_by('-created_at'))
