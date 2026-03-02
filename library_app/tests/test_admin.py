from django.test import TestCase
from django.urls import reverse


class AdminWorkflowTests(TestCase):
    def test_add_and_remove_blocked_date(self):
        add_res = self.client.post(
            reverse('api_add_blocked_date'),
            data={'date': '2026-04-01', 'reason': 'Holiday'},
            content_type='application/json',
        )
        self.assertEqual(add_res.status_code, 200)

        remove_res = self.client.post(
            reverse('api_remove_blocked_date'),
            data={'date': '2026-04-01'},
            content_type='application/json',
        )
        self.assertEqual(remove_res.status_code, 200)
