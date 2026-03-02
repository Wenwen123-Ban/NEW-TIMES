from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Book(models.Model):
    STATUS_AVAILABLE = 'Available'
    STATUS_RESERVED = 'Reserved'
    STATUS_BORROWED = 'Borrowed'

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_RESERVED, 'Reserved'),
        (STATUS_BORROWED, 'Borrowed'),
    ]

    book_no = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)

    def __str__(self):
        return f'{self.book_no} - {self.title}'


class ReservationTransaction(models.Model):
    STATUS_RESERVED = 'Reserved'
    STATUS_UNAVAILABLE = 'Unavailable'
    STATUS_CANCELLED = 'Cancelled'
    STATUS_EXPIRED = 'Expired'

    STATUS_CHOICES = [
        (STATUS_RESERVED, 'Reserved'),
        (STATUS_UNAVAILABLE, 'Unavailable'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='transactions')
    school_id = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RESERVED)
    date = models.DateTimeField(default=timezone.now)
    expiry = models.DateTimeField(null=True, blank=True)
    borrower_name = models.CharField(max_length=255, blank=True)
    pickup_location = models.CharField(max_length=255, blank=True)
    pickup_schedule = models.CharField(max_length=50, blank=True)
    reservation_note = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['school_id', 'status']),
            models.Index(fields=['book', 'status']),
        ]

    def clean(self):
        self.school_id = str(self.school_id or '').strip().lower()
        if not self.school_id:
            raise ValidationError({'school_id': 'school_id is required.'})
        if self.status == self.STATUS_RESERVED and ReservationTransaction.objects.exclude(pk=self.pk).filter(
            school_id=self.school_id,
            book=self.book,
            status=self.STATUS_RESERVED,
        ).exists():
            raise ValidationError('You already have an active reservation for this book.')

    @classmethod
    def cleanup_expired_for_user(cls, school_id: str):
        normalized = str(school_id or '').strip().lower()
        now = timezone.now()
        changed = False
        qs = cls.objects.select_related('book').filter(school_id=normalized, status=cls.STATUS_RESERVED, expiry__isnull=False)
        for tx in qs:
            if tx.expiry and now > tx.expiry:
                tx.status = cls.STATUS_EXPIRED
                tx.save(update_fields=['status'])
                if tx.book.status == Book.STATUS_RESERVED:
                    tx.book.status = Book.STATUS_AVAILABLE
                    tx.book.save(update_fields=['status'])
                changed = True
        return changed

    @classmethod
    def reserve_book(cls, *, book_no: str, school_id: str, borrower_name: str = '', pickup_location: str = '', pickup_schedule: str = '', reservation_note: str = ''):
        with transaction.atomic():
            normalized = str(school_id or '').strip().lower()
            cls.cleanup_expired_for_user(normalized)

            active = cls.objects.filter(school_id=normalized, status=cls.STATUS_RESERVED)
            if active.filter(book__book_no=book_no).exists():
                raise ValidationError('You already have an active reservation for this book.')
            if active.count() >= 5:
                raise ValidationError('Reservation limit reached (5 max).')

            book = Book.objects.select_for_update().filter(book_no=book_no).first()
            if not book or book.status == Book.STATUS_BORROWED:
                raise ValidationError('Unavailable')

            tx = cls.objects.create(
                book=book,
                school_id=normalized,
                status=cls.STATUS_RESERVED,
                date=timezone.now(),
                expiry=None,
                borrower_name=str(borrower_name or '').strip(),
                pickup_location=str(pickup_location or '').strip(),
                pickup_schedule=str(pickup_schedule or '').strip(),
                reservation_note=str(reservation_note or '').strip(),
            )
            if book.status != Book.STATUS_RESERVED:
                book.status = Book.STATUS_RESERVED
                book.save(update_fields=['status'])
            return tx

    @classmethod
    def cancel_reservation(cls, *, book_no: str, school_id: str):
        normalized = str(school_id or '').strip().lower()
        now = timezone.now()
        with transaction.atomic():
            qs = cls.objects.select_for_update().select_related('book').filter(
                book__book_no=book_no,
                school_id=normalized,
                status__in=[cls.STATUS_RESERVED, cls.STATUS_UNAVAILABLE],
            )
            if not qs.exists():
                return False
            for tx in qs:
                tx.status = cls.STATUS_CANCELLED
                tx.cancelled_at = now
                tx.save(update_fields=['status', 'cancelled_at'])
                if tx.book.status == Book.STATUS_RESERVED:
                    tx.book.status = Book.STATUS_AVAILABLE
                    tx.book.save(update_fields=['status'])
            return True
