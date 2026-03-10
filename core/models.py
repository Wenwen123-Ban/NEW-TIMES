import uuid
from django.db import models


class UserProfile(models.Model):
    school_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    password = models.CharField(max_length=255)
    category = models.CharField(max_length=50, default='Student')
    photo = models.CharField(max_length=255, default='default.png')
    status = models.CharField(max_length=20, default='approved')
    is_staff = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True)
    year_level = models.CharField(max_length=10, blank=True)
    school_level = models.CharField(max_length=20, blank=True)
    course = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lbas_users'


class Book(models.Model):
    book_no = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=30, default='Available')
    category = models.CharField(max_length=80, default='General')

    class Meta:
        db_table = 'lbas_books'


class Transaction(models.Model):
    book_no = models.CharField(max_length=50)
    title = models.CharField(max_length=255, blank=True)
    school_id = models.CharField(max_length=50)
    borrower_name = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=30)
    date = models.DateTimeField(auto_now_add=True)
    expiry = models.DateField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    pickup_schedule = models.CharField(max_length=30, blank=True)
    pickup_location = models.CharField(max_length=100, blank=True)
    reservation_note = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    contact_type = models.CharField(max_length=10, blank=True)
    request_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    approved_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'lbas_transactions'


class RegistrationRequest(models.Model):
    request_id = models.CharField(max_length=100, unique=True)
    request_number = models.CharField(max_length=10, blank=True)
    name = models.CharField(max_length=150)
    school_id = models.CharField(max_length=50)
    year_level = models.CharField(max_length=10)
    school_level = models.CharField(max_length=20)
    course = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=255)
    photo = models.CharField(max_length=255, default='default.png')
    status = models.CharField(max_length=20, default='pending')
    reviewed_by = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'lbas_registration_requests'


class NewsPost(models.Model):
    post_id = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    body = models.TextField()
    image_filename = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    author = models.CharField(max_length=150, default='Admin')

    class Meta:
        db_table = 'lbas_news'


class HomeCard(models.Model):
    card_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)

    class Meta:
        db_table = 'lbas_home_cards'


class DateRestriction(models.Model):
    date = models.DateField(unique=True)
    action = models.CharField(max_length=10)
    reason = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lbas_date_restrictions'


class SystemLog(models.Model):
    event = models.CharField(max_length=50)
    school_id = models.CharField(max_length=50, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    month = models.CharField(max_length=7)

    class Meta:
        db_table = 'lbas_logs'
