from datetime import date, timedelta

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from turnos.models import ConfiguracionTurno
from turnos.rotacion import HORARIOS_TURNOS, obtener_semanas_calendario


def home(request):
    """Vista de inicio para la aplicación con integración de calendario."""
    context = {}
    if request.user.is_authenticated:
        config = ConfiguracionTurno.obtener_activa()

        try:
            offset = int(request.GET.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0

        # Fecha de referencia a partir de hoy con el offset de semanas
        fecha_referencia = date.today() + timedelta(weeks=offset)
        semanas = obtener_semanas_calendario(fecha_referencia, num_semanas=4, config=config)

        context.update(
            {
                "config": config,
                "semanas": semanas,
                "offset": offset,
                "offset_prev": offset - 1,
                "offset_next": offset + 1,
                "offset_plus_3": offset + 3,
                "offset_minus_3": offset - 3,
                "fecha_referencia": fecha_referencia,
                "horarios_turnos": HORARIOS_TURNOS,
            }
        )

    return render(request, "home.html", context)


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
