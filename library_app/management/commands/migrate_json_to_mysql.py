from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password

from library_app.models import Student, Book, Reservation, Admin
from library_app.services.json_store import read_json


class Command(BaseCommand):
    help = 'Imports JSON test data into Django models (for MySQL migration phase).'

    def handle(self, *args, **options):
        if settings.USE_JSON_DATA:
            self.stdout.write(self.style.WARNING('USE_JSON_DATA=true. Skipping DB import by design.'))
            return

        users = read_json('users')
        books = read_json('books')
        admins = read_json('admins')
        transactions = read_json('transactions')

        for user in users:
            sid = str(user.get('school_id', '')).strip()
            if not sid:
                continue
            Student.objects.update_or_create(
                id=sid,
                defaults={
                    'name': str(user.get('name', sid)).strip(),
                    'department': str(user.get('category', 'General')).strip(),
                },
            )

        for row in books:
            bid = str(row.get('book_no', '')).strip()
            if not bid:
                continue
            Book.objects.update_or_create(
                book_id=bid,
                defaults={
                    'title': str(row.get('title', '')).strip(),
                    'author': str(row.get('author', 'Unknown')).strip(),
                    'status': 'Borrowed' if str(row.get('status', '')).lower() == 'borrowed' else 'Available',
                },
            )

        for row in admins:
            username = str(row.get('school_id', '')).strip()
            if not username:
                continue
            raw = str(row.get('password', ''))
            Admin.objects.update_or_create(
                username=username,
                defaults={'password_hash': raw if raw.startswith('pbkdf2_') else make_password(raw)},
            )

        for row in transactions:
            status = str(row.get('status', '')).upper()
            if status not in {'PENDING', 'APPROVED', 'CANCELLED', 'RESERVED'}:
                continue
            sid = str(row.get('school_id', '')).strip()
            bid = str(row.get('book_no', '')).strip()
            date = row.get('pickup_date') or row.get('date', '')[:10]
            if not sid or not bid or not date:
                continue
            if not Student.objects.filter(id=sid).exists() or not Book.objects.filter(book_id=bid).exists():
                continue
            Reservation.objects.create(
                student_id=sid,
                book_id=bid,
                pickup_date=date,
                status='PENDING' if status == 'RESERVED' else status,
                approved_by=row.get('approved_by'),
            )

        self.stdout.write(self.style.SUCCESS('JSON migration complete.'))
