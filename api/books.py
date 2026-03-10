from django.http import JsonResponse
from core.models import Book
from .utils import list_response


def books_list(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    return list_response(Book.objects.all().order_by('book_no'))
