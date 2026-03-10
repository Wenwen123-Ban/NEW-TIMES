import json
from django.forms.models import model_to_dict
from django.http import JsonResponse


def parse_json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def list_response(queryset):
    return JsonResponse([model_to_dict(obj) for obj in queryset], safe=False)
