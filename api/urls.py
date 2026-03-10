from django.urls import path
from . import (
    auth,
    books,
    users,
    registration,
    tickets,
    leaderboard,
    news,
    home_cards,
    date_restrictions,
    courses,
    transactions,
)

urlpatterns = [
    path('auth/login', auth.login),
    path('books', books.books_list),
    path('users', users.users_list),
    path('registration-requests', registration.registration_requests),
    path('tickets', tickets.tickets),
    path('leaderboard', leaderboard.leaderboard),
    path('news', news.news_list),
    path('home-cards', home_cards.home_cards),
    path('date-restrictions', date_restrictions.date_restrictions),
    path('courses', courses.courses),
    path('transactions', transactions.transactions_list),
]
