from datetime import date, time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils import timezone

from turnos.ical import descargar_feed_ical
from turnos.models import ConfiguracionTurno, ReubicacionClase


def usuario_puede_gestionar(user) -> bool:
    """Verifica si el usuario es pau o admin/superuser para gestionar turnos y ajustes."""
    return user.is_authenticated and (user.username in ("pau", "admin") or user.is_superuser)


@login_required(login_url="login")
def configurar_turnos(request):
    """Permite a Pau o admin modificar la fecha base y el turno de anclaje."""
    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden modificar los turnos."
        )

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


@login_required(login_url="login")
def configurar_calendario_uni(request):
    """Permite configurar la URL del calendario iCal universitario y sincronizarlo."""
    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden configurar el calendario universitario."
        )

    config = ConfiguracionTurno.obtener_activa()
    error_mensaje = None
    exito_mensaje = None

    if request.method == "POST":
        url_ical = request.POST.get("url_ical_uni", "").strip()
        config.url_ical_uni = url_ical

        if url_ical:
            try:
                contenido = descargar_feed_ical(url_ical)
                config.contenido_ical_cache = contenido
                config.sincronizado_el = timezone.now()
                exito_mensaje = "Calendario universitario sincronizado con éxito."
            except Exception as e:  # noqa: BLE001 - atrapar errores de red/timeout/parseo al descargar
                error_mensaje = f"URL guardada, pero no se pudo descargar el feed: {e}"
        else:
            config.contenido_ical_cache = ""
            config.sincronizado_el = None
            exito_mensaje = "URL eliminada. Sincronización desactivada."

        config.save()
        if not error_mensaje:
            return redirect("/?vista=semana")

    return render(
        request,
        "turnos/configurar_ical.html",
        {
            "config": config,
            "error": error_mensaje,
            "exito": exito_mensaje,
        },
    )


@login_required(login_url="login")
def reubicar_clase_view(request):
    """Permite reubicar una clase universitaria solapada a un momento estrictamente posterior."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden reubicar clases."
        )

    uid_evento = request.POST.get("uid_evento", "").strip()
    fecha_orig_str = request.POST.get("fecha_original", "").strip()
    hora_orig_str = request.POST.get("hora_inicio_original", "").strip()
    nueva_fecha_str = request.POST.get("nueva_fecha", "").strip()
    nueva_hora_str = request.POST.get("nueva_hora_inicio", "").strip()

    if not (uid_evento and fecha_orig_str and hora_orig_str and nueva_fecha_str and nueva_hora_str):
        return HttpResponseBadRequest("Faltan parámetros obligatorios para la reubicación.")

    try:
        fecha_orig = date.fromisoformat(fecha_orig_str)
        hora_orig = time.fromisoformat(hora_orig_str)
        nueva_fecha = date.fromisoformat(nueva_fecha_str)
        nueva_hora = time.fromisoformat(nueva_hora_str)
    except ValueError:
        return HttpResponseBadRequest("Formato de fecha u hora inválido.")

    # Validación estricta: nueva fecha y hora debe ser estrictamente posterior al inicio original
    es_posterior = (nueva_fecha > fecha_orig) or (
        nueva_fecha == fecha_orig and nueva_hora > hora_orig
    )
    if not es_posterior:
        return HttpResponseBadRequest(
            "La nueva fecha y hora debe ser estrictamente posterior al inicio original de la clase."
        )

    config = ConfiguracionTurno.obtener_activa()
    ReubicacionClase.objects.update_or_create(
        configuracion=config,
        uid_evento=uid_evento,
        fecha_original=fecha_orig,
        defaults={
            "hora_inicio_original": hora_orig,
            "nueva_fecha": nueva_fecha,
            "nueva_hora_inicio": nueva_hora,
        },
    )

    return redirect(f"/?vista=semana&fecha={nueva_fecha.isoformat()}")


@login_required(login_url="login")
def restablecer_clase_view(request):
    """Permite restablecer una clase universitaria reubicada a su horario original iCal."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden restablecer clases."
        )

    uid_evento = request.POST.get("uid_evento", "").strip()
    fecha_orig_str = request.POST.get("fecha_original", "").strip()

    if not (uid_evento and fecha_orig_str):
        return HttpResponseBadRequest("Faltan parámetros obligatorios para el restablecimiento.")

    try:
        fecha_orig = date.fromisoformat(fecha_orig_str)
    except ValueError:
        return HttpResponseBadRequest("Formato de fecha original inválido.")

    config = ConfiguracionTurno.obtener_activa()
    ReubicacionClase.objects.filter(
        configuracion=config,
        uid_evento=uid_evento,
        fecha_original=fecha_orig,
    ).delete()

    return redirect(f"/?vista=semana&fecha={fecha_orig.isoformat()}")
