from django.urls import path
from . import views

urlpatterns = [
    path('', views.reserve_page, name='reserve'),
    path('reserve/', views.reserve_page, name='reserve_alias'),
    path('admin_dashboard/', views.admin_dashboard_page, name='admin_dashboard'),

    path('api/login', views.api_login, name='api_login'),
    path('api/books', views.api_books, name='api_books'),
    path('api/users', views.api_users, name='api_users'),
    path('api/admins', views.api_admins, name='api_admins'),
    path('api/transactions', views.api_transactions, name='api_transactions'),
    path('api/categories', views.api_categories, name='api_categories'),
    path('api/user/<str:s_id>', views.api_user_detail, name='api_user_detail'),

    path('api/reserve', views.api_reserve, name='api_reserve'),
    path('api/cancel_reservation', views.api_cancel_reservation, name='api_cancel_reservation'),
    path('api/admin/approve_reservation', views.api_approve_reservation, name='api_approve_reservation'),
    path('api/admin/blocked_dates/add', views.api_add_blocked_date, name='api_add_blocked_date'),
    path('api/admin/blocked_dates/remove', views.api_remove_blocked_date, name='api_remove_blocked_date'),
    path('api/admin/hash_passwords', views.api_hash_admin_passwords, name='api_hash_admin_passwords'),
]
