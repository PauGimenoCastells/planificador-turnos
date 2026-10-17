from django.shortcuts import render


def home(request):
    """Vista de inicio para la aplicación."""
    return render(request, "home.html")
