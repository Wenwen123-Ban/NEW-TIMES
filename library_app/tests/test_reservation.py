from django.test import TestCase
from django.urls import reverse


class ReservationValidationTests(TestCase):
    def test_reject_weekend_pickup(self):
        response = self.client.post(
            reverse('api_reserve'),
            data={'school_id': '2025-001130', 'book_no': 'MAT-001', 'pickup_date': '2026-03-08'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Weekend', response.json()['message'])
