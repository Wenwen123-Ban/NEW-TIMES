from django.urls import path

from . import views

urlpatterns = [
    path('reserve', views.reserve, name='reserve'),
    path('cancel_reservation', views.cancel_reservation, name='cancel_reservation'),
]
