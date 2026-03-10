"""
Run once before presentation:
    python manage.py seed_demo
"""
from django.core.management.base import BaseCommand
from core.models import UserProfile, Book, HomeCard

BOOKS = {
    'Science': [
        ('SCI-001', 'Introduction to Physics'),
        ('SCI-002', 'Biology: Life on Earth'),
        ('SCI-003', 'Chemistry Fundamentals'),
        ('SCI-004', 'Earth Science Essentials'),
        ('SCI-005', 'Environmental Science Today'),
    ],
    'Mathematics': [
        ('MATH-001', 'Algebra and Trigonometry'),
        ('MATH-002', 'Calculus for Beginners'),
        ('MATH-003', 'Statistics and Probability'),
        ('MATH-004', 'Discrete Mathematics'),
        ('MATH-005', 'Linear Algebra Basics'),
    ],
    'Literature': [
        ('LIT-001', 'Philippine Literature Anthology'),
        ('LIT-002', 'World Classics Collection'),
        ('LIT-003', 'Introduction to Poetry'),
        ('LIT-004', 'Fiction Writing Workshop'),
        ('LIT-005', 'Reading and Critical Thinking'),
    ],
    'General': [
        ('GEN-001', 'Research Methods for Students'),
        ('GEN-002', 'Study Skills and Time Management'),
        ('GEN-003', 'Introduction to Computer Science'),
        ('GEN-004', 'Ethics and Values Education'),
        ('GEN-005', 'Practical Communication Skills'),
    ],
}


class Command(BaseCommand):
    help = 'Seeds demo data for LBAS presentation'

    def handle(self, *args, **kwargs):
        _, created = UserProfile.objects.get_or_create(
            school_id='admin',
            defaults={
                'name': 'System Administrator',
                'password': 'admin',
                'category': 'Staff',
                'is_staff': True,
                'status': 'approved',
                'photo': 'default.png',
            },
        )
        self.stdout.write(f"  Admin: {'created' if created else 'already exists'}")

        _, created = UserProfile.objects.get_or_create(
            school_id='2024-00001',
            defaults={
                'name': 'Demo Student',
                'password': 'student123',
                'category': 'Student',
                'is_staff': False,
                'status': 'approved',
                'photo': 'default.png',
                'year_level': '1',
                'school_level': 'college',
                'course': 'BSIT',
            },
        )
        self.stdout.write(f"  Student: {'created' if created else 'already exists'}")

        book_count = 0
        for category, book_list in BOOKS.items():
            for book_no, title in book_list:
                _, created = Book.objects.get_or_create(
                    book_no=book_no,
                    defaults={'title': title, 'category': category, 'status': 'Available'},
                )
                if created:
                    book_count += 1
        self.stdout.write(f'  Books added: {book_count} (skipped existing)')

        for i in range(1, 5):
            HomeCard.objects.get_or_create(
                card_id=i,
                defaults={
                    'title': f'Library Info {i}',
                    'body': 'Update this card from the admin dashboard.',
                },
            )

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Demo data loaded. Login: admin/admin or 2024-00001/student123'
        ))
