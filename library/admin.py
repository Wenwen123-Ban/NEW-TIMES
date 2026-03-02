from django.contrib import admin
from .models import Book, ReservationTransaction

admin.site.register(Book)
admin.site.register(ReservationTransaction)
