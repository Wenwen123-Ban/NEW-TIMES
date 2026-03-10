from django.http import JsonResponse
from core.models import HomeCard
from .utils import list_response


def home_cards(request):
    return list_response(HomeCard.objects.all().order_by('card_id'))
