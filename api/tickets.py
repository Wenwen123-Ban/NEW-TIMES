from django.http import JsonResponse


def tickets(request):
    return JsonResponse({'items': [], 'message': 'Ticket endpoint ready for Django migration'})
