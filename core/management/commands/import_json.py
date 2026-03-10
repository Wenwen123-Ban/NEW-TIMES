"""
Optional: import existing JSON data into MySQL.
Run: python manage.py import_json
Only needed if you have real existing data to preserve.
For the demo presentation, just use seed_demo instead.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Placeholder importer for legacy JSON files'

    def handle(self, *args, **kwargs):
        self.stdout.write('Legacy JSON import placeholder. Use seed_demo for presentation data.')
