from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from turnos.models import ConfiguracionTurno


@login_required(login_url="login")
def configurar_turnos(request):
    """Permite a Pau modificar la fecha base y el turno de anclaje."""
    config = ConfiguracionTurno.obtener_activa()
    mensaje = None

    if request.method == "POST":
        fecha_base_str = request.POST.get("fecha_base", "").strip()
        turno_inicial = request.POST.get("turno_inicial", "").strip().upper()

        if fecha_base_str and turno_inicial in dict(ConfiguracionTurno.OPCIONES_TURNO):
            try:
                nueva_fecha = date.fromisoformat(fecha_base_str)
                config.fecha_base = nueva_fecha
                config.turno_inicial = turno_inicial
                config.save()
                return redirect("home")
            except ValueError:
                mensaje = "Formato de fecha inválido. Utilice AAAA-MM-DD."
        else:
            mensaje = "Datos inválidos. Compruebe los campos."

    return render(
        request,
        "turnos/configurar.html",
        {
            "config": config,
            "opciones_turno": ConfiguracionTurno.OPCIONES_TURNO,
            "error": mensaje,
        },
    )
