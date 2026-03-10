from django.http import JsonResponse
from core.models import NewsPost
from .utils import list_response


def news_list(request):
    return list_response(NewsPost.objects.all().order_by('-date'))
