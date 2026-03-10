from django.http import JsonResponse
from django.db.models import Count
from core.models import Transaction


def leaderboard(request):
    data = (
        Transaction.objects.values('school_id')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )
    return JsonResponse(list(data), safe=False)
