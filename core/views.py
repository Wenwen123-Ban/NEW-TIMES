from django.shortcuts import render, redirect


def index_gateway(request):
    return redirect('/lbas')


def admin_site(request):
    return render(request, 'admin_dashboard.html')


def lbas_site(request):
    return render(request, 'LBAS.html')
