from django.http import JsonResponse


def courses(request):
    return JsonResponse([
        {'code': 'BSIT', 'name': 'Bachelor of Science in Information Technology'},
        {'code': 'BSCS', 'name': 'Bachelor of Science in Computer Science'},
    ], safe=False)
