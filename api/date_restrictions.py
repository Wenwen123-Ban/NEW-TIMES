from django.http import JsonResponse
from core.models import DateRestriction
from .utils import list_response


def date_restrictions(request):
    return list_response(DateRestriction.objects.all().order_by('date'))
