from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render


def home(request):
    """Vista de inicio para la aplicación."""
    return render(request, "home.html")


def login_view(request):
    """Vista de inicio de sesión de usuarios."""
    if request.user.is_authenticated:
        return redirect("home")

    error_message = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            error_message = "Nombre de usuario o contraseña incorrectos."

    return render(request, "login.html", {"error": error_message})


def logout_view(request):
    """Vista de cierre de sesión."""
    logout(request)
    return redirect("home")
