from datetime import date, datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.shortcuts import redirect, render
from django.utils import timezone

from turnos.ical import descargar_feed_ical
from turnos.models import (
    ActividadAutobus,
    Cita,
    ConfiguracionTurno,
    ExcepcionTurnoSemana,
    FestivoParada,
    ReubicacionClase,
    VigenciaRotacion,
)
from turnos.rotacion import (
    FESTIVOS_OFICIALES_MARTORELL_2026,
    consultar_festivo_dia,
    generar_bloques_dia_turno,
    obtener_franjas_disponibles_semana,
    obtener_turno_dia,
)

CATALOGO_ACTIVIDADES = ["siesta", "lectura", "reflexion", "videojuegos", "videos"]


def purgar_o_caducar_citas_vencidas() -> int:
    """
    Caduca automáticamente las solicitudes de cita que no hayan sido confirmadas
    12 horas antes del inicio programado de la cita.
    """
    ahora = timezone.now()
    caducadas_count = 0
    citas_solicitadas = Cita.objects.filter(estado="solicitada")
    for cita in citas_solicitadas:
        inicio_dt = datetime.combine(cita.fecha, cita.hora_inicio)
        if timezone.is_naive(inicio_dt):
            inicio_dt = timezone.make_aware(inicio_dt, timezone.get_current_timezone())
        if ahora >= inicio_dt - timedelta(hours=12):
            cita.estado = "caducada"
            cita.save(update_fields=["estado"])
            caducadas_count += 1
    return caducadas_count


def usuario_puede_gestionar(user) -> bool:
    """Verifica si el usuario es pau o admin/superuser para gestionar turnos y ajustes."""
    return user.is_authenticated and (user.username in ("pau", "admin") or user.is_superuser)


@login_required(login_url="login")
def configurar_turnos(request):
    """Permite a Pau o admin modificar la fecha base, el turno de anclaje y las vigencias de rotación."""
    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden modificar los turnos."
        )

    config = ConfiguracionTurno.obtener_activa()
    mensaje = None

    if request.method == "POST":
        accion = request.POST.get("accion", "").strip()
        if accion == "crear_vigencia" or (
            "fecha_inicio" in request.POST and "fecha_base" not in request.POST
        ):
            fecha_inicio_str = request.POST.get("fecha_inicio", "").strip()
            turno_inicial = request.POST.get("turno_inicial", "").strip().upper()
            if fecha_inicio_str and turno_inicial in ("A", "B", "C"):
                try:
                    fecha_inicio = date.fromisoformat(fecha_inicio_str)
                    VigenciaRotacion.objects.update_or_create(
                        fecha_inicio=fecha_inicio,
                        defaults={"turno_inicial": turno_inicial},
                    )
                    return redirect(request.path)
                except ValueError:
                    mensaje = "Formato de fecha inválido. Utilice AAAA-MM-DD."
            else:
                mensaje = "Datos inválidos para la nueva vigencia de rotación."
        else:
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

    vigencias = list(VigenciaRotacion.objects.order_by("fecha_inicio"))

    return render(
        request,
        "turnos/configurar_turnos.html",
        {
            "config": config,
            "vigencias": vigencias,
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


@login_required(login_url="login")
def solicitar_cita_view(request):
    """Permite a un usuario solicitar una cita durante una franja disponible de Pau."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    fecha_str = request.POST.get("fecha", "").strip()
    hora_inicio_str = request.POST.get("hora_inicio", "").strip()
    hora_fin_str = request.POST.get("hora_fin", "").strip()
    motivo = request.POST.get("motivo", "").strip()

    if not (fecha_str and hora_inicio_str and hora_fin_str and motivo):
        return HttpResponseBadRequest("Faltan parámetros obligatorios para solicitar la cita.")

    if len(motivo) > 250:
        return HttpResponseBadRequest(
            "El motivo no puede superar estrictamente 250 caracteres (enviados: "
            f"{len(motivo)} caracteres)."
        )

    try:
        fecha = date.fromisoformat(fecha_str)
        hora_inicio = time.fromisoformat(hora_inicio_str)
        hora_fin = time.fromisoformat(hora_fin_str)
    except ValueError:
        return HttpResponseBadRequest("Formato de fecha u hora inválido.")

    if hora_fin <= hora_inicio:
        return HttpResponseBadRequest(
            "La hora de fin debe ser estrictamente posterior a la hora de inicio."
        )

    # Validar que no sea en el pasado y con al menos 24 horas de antelación
    ahora = timezone.now()
    inicio_dt = datetime.combine(fecha, hora_inicio)
    if timezone.is_naive(inicio_dt):
        inicio_dt = timezone.make_aware(inicio_dt, timezone.get_current_timezone())

    if inicio_dt <= ahora:
        return HttpResponseBadRequest("No se pueden solicitar citas en el pasado.")

    if inicio_dt < ahora + timedelta(hours=24):
        return HttpResponseBadRequest(
            "Solo se pueden solicitar citas con un mínimo de 24 horas de antelación."
        )

    # Validar que la cita cae dentro de una franja disponible de Pau
    franjas_sem = obtener_franjas_disponibles_semana(fecha)
    franjas_dia = franjas_sem.get(fecha, [])

    req_ini = hora_inicio.hour * 60 + hora_inicio.minute
    req_fin = hora_fin.hour * 60 + hora_fin.minute

    cae_en_disponible = any(
        f["minuto_inicio"] <= req_ini and req_fin <= f["minuto_fin"] for f in franjas_dia
    )

    if not cae_en_disponible:
        return HttpResponseBadRequest(
            "La cita solicitada no cae dentro de una franja disponible de Pau para ese día."
        )

    Cita.objects.create(
        solicitante=request.user,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        motivo=motivo,
        estado="solicitada",
    )

    return redirect(f"/?vista=semana&fecha={fecha.isoformat()}")


@login_required(login_url="login")
def confirmar_cita_view(request):
    """Permite a Pau o administradores confirmar una cita solicitada."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden confirmar citas."
        )

    cita_id = request.POST.get("cita_id", "").strip()
    if not cita_id:
        return HttpResponseBadRequest("Falta el identificador de la cita.")

    try:
        cita = Cita.objects.get(id=cita_id)
    except (Cita.DoesNotExist, ValueError):
        return HttpResponseBadRequest("Cita no encontrada.")

    cita.estado = "confirmada"
    cita.save()

    return redirect(f"/?vista=semana&fecha={cita.fecha.isoformat()}")


@login_required(login_url="login")
def rechazar_cita_view(request):
    """Permite a Pau o administradores rechazar una cita solicitada."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden rechazar citas."
        )

    cita_id = request.POST.get("cita_id", "").strip()
    if not cita_id:
        return HttpResponseBadRequest("Falta el identificador de la cita.")

    try:
        cita = Cita.objects.get(id=cita_id)
    except (Cita.DoesNotExist, ValueError):
        return HttpResponseBadRequest("Cita no encontrada.")

    cita.estado = "rechazada"
    cita.save()

    return redirect(f"/?vista=semana&fecha={cita.fecha.isoformat()}")


@login_required(login_url="login")
def cancelar_cita_view(request):
    """Permite al solicitante (o a Pau/Admin) cancelar una cita en cualquier momento."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    cita_id = request.POST.get("cita_id", "").strip()
    if not cita_id:
        return HttpResponseBadRequest("Falta el identificador de la cita.")

    try:
        cita = Cita.objects.get(id=cita_id)
    except (Cita.DoesNotExist, ValueError):
        return HttpResponseBadRequest("Cita no encontrada.")

    es_dueno = cita.solicitante == request.user
    es_gestor = usuario_puede_gestionar(request.user)
    if not (es_dueno or es_gestor):
        return HttpResponseForbidden("Acceso denegado: no tiene permisos para cancelar esta cita.")

    if cita.estado not in ("solicitada", "confirmada", "contraoferta"):
        return HttpResponseBadRequest("La cita ya no puede ser cancelada en su estado actual.")

    cita.estado = "cancelada"
    cita.save()

    return redirect(f"/?vista=semana&fecha={cita.fecha.isoformat()}")


@login_required(login_url="login")
def contraofertar_cita_view(request):
    """Permite a Pau o administradores enviar una contraoferta con horario alternativo."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden enviar contraofertas."
        )

    cita_id = request.POST.get("cita_id", "").strip()
    nueva_fecha_str = request.POST.get("nueva_fecha", "").strip()
    nueva_hora_ini_str = request.POST.get("nueva_hora_inicio", "").strip()
    nueva_hora_fin_str = request.POST.get("nueva_hora_fin", "").strip()
    mensaje = request.POST.get("mensaje_contraoferta", "").strip()

    if not (cita_id and nueva_fecha_str and nueva_hora_ini_str and nueva_hora_fin_str):
        return HttpResponseBadRequest("Faltan parámetros obligatorios para la contraoferta.")

    if len(mensaje) > 250:
        return HttpResponseBadRequest(
            f"El mensaje de contraoferta no puede superar 250 caracteres (enviados: {len(mensaje)})."
        )

    try:
        nueva_fecha = date.fromisoformat(nueva_fecha_str)
        nueva_hora_ini = time.fromisoformat(nueva_hora_ini_str)
        nueva_hora_fin = time.fromisoformat(nueva_hora_fin_str)
    except ValueError:
        return HttpResponseBadRequest("Formato de fecha u hora inválido.")

    if nueva_hora_fin <= nueva_hora_ini:
        return HttpResponseBadRequest(
            "La hora de fin debe ser estrictamente posterior a la hora de inicio."
        )

    # Validar antelación mínima de 12 horas (R5)
    ahora = timezone.now()
    propuesta_dt = datetime.combine(nueva_fecha, nueva_hora_ini)
    if timezone.is_naive(propuesta_dt):
        propuesta_dt = timezone.make_aware(propuesta_dt, timezone.get_current_timezone())

    if ahora <= propuesta_dt < ahora + timedelta(hours=12):
        return HttpResponseBadRequest(
            "La contraoferta debe realizarse con al menos 12 horas de antelación respecto a la hora propuesta."
        )

    # Validar que la contraoferta cae dentro de una franja disponible de Pau (R5)
    franjas_sem = obtener_franjas_disponibles_semana(nueva_fecha)
    franjas_dia = franjas_sem.get(nueva_fecha, [])
    req_ini = nueva_hora_ini.hour * 60 + nueva_hora_ini.minute
    req_fin = nueva_hora_fin.hour * 60 + nueva_hora_fin.minute

    cae_en_disponible = any(
        f["minuto_inicio"] <= req_ini and req_fin <= f["minuto_fin"] for f in franjas_dia
    )
    if not cae_en_disponible:
        return HttpResponseBadRequest(
            "La propuesta no cae dentro de una franja disponible de Pau para ese día."
        )

    try:
        cita = Cita.objects.get(id=cita_id)
    except (Cita.DoesNotExist, ValueError):
        return HttpResponseBadRequest("Cita no encontrada.")

    if cita.estado != "solicitada":
        return HttpResponseBadRequest(
            "Solo se pueden enviar contraofertas a citas en estado solicitada."
        )

    cita.estado = "contraoferta"
    cita.fecha_propuesta = nueva_fecha
    cita.hora_inicio_propuesta = nueva_hora_ini
    cita.hora_fin_propuesta = nueva_hora_fin
    cita.mensaje_contraoferta = mensaje
    cita.save()

    return redirect(f"/?vista=semana&fecha={cita.fecha.isoformat()}")


@login_required(login_url="login")
def responder_contraoferta_view(request):
    """Permite al solicitante aceptar o rechazar una contraoferta recibida de Pau."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    cita_id = request.POST.get("cita_id", "").strip()
    accion = request.POST.get("accion", "").strip().lower()

    if not (cita_id and accion):
        return HttpResponseBadRequest("Faltan parámetros obligatorios.")

    try:
        cita = Cita.objects.get(id=cita_id)
    except (Cita.DoesNotExist, ValueError):
        return HttpResponseBadRequest("Cita no encontrada.")

    if cita.solicitante != request.user:
        return HttpResponseForbidden(
            "Acceso denegado: solo el solicitante de la cita puede responder a la contraoferta."
        )

    if cita.estado != "contraoferta":
        return HttpResponseBadRequest("La cita no tiene una contraoferta pendiente de respuesta.")

    if accion == "aceptar":
        if not (cita.fecha_propuesta and cita.hora_inicio_propuesta and cita.hora_fin_propuesta):
            return HttpResponseBadRequest("Datos de la propuesta incompletos.")
        cita.fecha = cita.fecha_propuesta
        cita.hora_inicio = cita.hora_inicio_propuesta
        cita.hora_fin = cita.hora_fin_propuesta
        cita.estado = "confirmada"
        cita.save()
    elif accion == "rechazar":
        cita.estado = "rechazada"
        cita.save()
    else:
        return HttpResponseBadRequest("Acción no válida. Debe ser 'aceptar' o 'rechazar'.")

    return redirect(f"/?vista=semana&fecha={cita.fecha.isoformat()}")


@login_required(login_url="login")
def guardar_actividades_bus_view(request):
    """Permite a Pau registrar o actualizar las actividades realizadas en un trayecto de autobús completado."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden registrar actividades."
        )

    fecha_str = request.POST.get("fecha", "").strip()
    tipo_bus = request.POST.get("tipo_bus", "").strip()
    actividades = request.POST.getlist("actividades")

    if not (fecha_str and tipo_bus):
        return HttpResponseBadRequest("Faltan parámetros obligatorios (fecha y tipo_bus).")

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return HttpResponseBadRequest("Formato de fecha inválido.")

    if tipo_bus not in ("bus_ida", "bus_vuelta"):
        return HttpResponseBadRequest(
            "Tipo de autobús inválido. Debe ser 'bus_ida' o 'bus_vuelta'."
        )

    # Validar que todas las actividades pertenecen al catálogo permitido (R3 - Criterio Portante)
    for act in actividades:
        if act not in CATALOGO_ACTIVIDADES:
            return HttpResponseBadRequest(
                f"Actividad no permitida: '{act}'. Las opciones válidas son: {', '.join(CATALOGO_ACTIVIDADES)}."
            )

    # Validar que el trayecto ya ha finalizado (R2)
    info_turno = obtener_turno_dia(fecha)
    if info_turno.get("es_descanso") or not info_turno.get("codigo"):
        return HttpResponseBadRequest("No existen trayectos de autobús en días de descanso.")

    bloques = generar_bloques_dia_turno(info_turno["codigo"], fecha)
    bloque_bus = next((b for b in bloques if b["tipo"] == tipo_bus), None)
    if not bloque_bus:
        return HttpResponseBadRequest("No se encontró el trayecto de autobús para el día indicado.")

    hora_fin = time.fromisoformat(bloque_bus["hora_fin_str"])
    fin_dt = datetime.combine(fecha, hora_fin)
    if timezone.is_naive(fin_dt):
        fin_dt = timezone.make_aware(fin_dt, timezone.get_current_timezone())

    if fin_dt > timezone.now():
        return HttpResponseBadRequest(
            "El registro de actividades solo se permite en trayectos de autobús que ya hayan finalizado."
        )

    actividades_limpias = list(dict.fromkeys(actividades))
    ActividadAutobus.objects.update_or_create(
        fecha=fecha,
        tipo_bus=tipo_bus,
        defaults={"actividades": actividades_limpias},
    )

    return redirect(f"/?vista=semana&fecha={fecha.isoformat()}")


@login_required(login_url="login")
def alternar_festivo_view(request):
    """
    Alterna o revierte el estado festivo/parada de un día (R3, R5).
    Disponible exclusivamente para Pau o superusuarios.
    """
    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden modificar los festivos."
        )

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    fecha_str = request.POST.get("fecha", "").strip()
    if not fecha_str:
        return HttpResponseBadRequest("Falta el parámetro fecha.")

    try:
        fecha_val = date.fromisoformat(fecha_str)
    except ValueError:
        return HttpResponseBadRequest("Formato de fecha inválido. Use YYYY-MM-DD.")

    accion = request.POST.get("accion", "").strip()
    motivo = request.POST.get("motivo", "").strip()

    es_oficial = fecha_val in FESTIVOS_OFICIALES_MARTORELL_2026

    if accion in ("revertir_laborable", "marcar_laborable"):
        # Guardar registro explícito con es_festivo=False para forzar día laborable (incluso en fin de semana o festivo oficial)
        fp, _ = FestivoParada.objects.update_or_create(
            fecha=fecha_val,
            defaults={
                "es_festivo": False,
                "motivo": motivo,
                "es_oficial": es_oficial,
            },
        )
    elif accion in ("marcar_festivo", "marcar_parada"):
        motivo_final = (
            motivo
            or FESTIVOS_OFICIALES_MARTORELL_2026.get(fecha_val)
            or "Parada de fábrica"
        )
        fp, _ = FestivoParada.objects.update_or_create(
            fecha=fecha_val,
            defaults={
                "es_festivo": True,
                "motivo": motivo_final,
                "es_oficial": es_oficial,
            },
        )
    else:
        # Alternancia automática según estado actual
        actual = consultar_festivo_dia(fecha_val)
        if (actual and actual.get("es_festivo")) or (
            fecha_val.weekday() in (5, 6) and (not actual or actual.get("es_festivo"))
        ):
            fp, _ = FestivoParada.objects.update_or_create(
                fecha=fecha_val,
                defaults={
                    "es_festivo": False,
                    "motivo": motivo,
                    "es_oficial": es_oficial,
                },
            )
        else:
            motivo_final = (
                motivo
                or FESTIVOS_OFICIALES_MARTORELL_2026.get(fecha_val)
                or "Parada de fábrica"
            )
            fp, _ = FestivoParada.objects.update_or_create(
                fecha=fecha_val,
                defaults={
                    "es_festivo": True,
                    "motivo": motivo_final,
                    "es_oficial": es_oficial,
                },
            )

    # Si es petición AJAX / JSON
    if (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    ):
        return JsonResponse(
            {
                "status": "ok",
                "fecha": str(fecha_val),
                "es_festivo": fp.es_festivo,
                "motivo": fp.motivo,
            }
        )

    # Redirección al calendario en la fecha modificada
    referer = request.META.get("HTTP_REFERER")
    if referer:
        return redirect(referer)
    return redirect(f"/?vista=mes&fecha={fecha_val.isoformat()}")


@login_required(login_url="login")
def cambiar_turno_semana_view(request):
    """
    Permite a Pau o superusuarios cambiar masivamente el turno de una semana completa desde el lunes (R2),
    o restablecer la rotación automática si se selecciona 'restablecer'.
    """
    if not usuario_puede_gestionar(request.user):
        return HttpResponseForbidden(
            "Acceso denegado: solo Pau o administradores pueden modificar el turno semanal."
        )

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    lunes_str = request.POST.get("lunes_semana", "").strip()
    if not lunes_str:
        return HttpResponseBadRequest("Falta el parámetro lunes_semana.")

    try:
        lunes_val = date.fromisoformat(lunes_str)
    except ValueError:
        return HttpResponseBadRequest("Formato de fecha inválido. Use YYYY-MM-DD.")

    # Asegurar que la fecha corresponde al lunes de esa semana
    lunes_val = lunes_val - timedelta(days=lunes_val.weekday())

    turno = request.POST.get("turno", "").strip().upper()

    if turno in ("A", "B", "C"):
        ExcepcionTurnoSemana.objects.update_or_create(
            lunes_semana=lunes_val,
            defaults={"turno": turno},
        )
    elif turno in ("", "RESTABLECER", "AUTO"):
        ExcepcionTurnoSemana.objects.filter(lunes_semana=lunes_val).delete()
    else:
        return HttpResponseBadRequest("Turno no válido. Debe ser A, B, C o restablecer.")

    if (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    ):
        return JsonResponse(
            {
                "status": "ok",
                "lunes_semana": str(lunes_val),
                "turno": turno if turno in ("A", "B", "C") else "auto",
            }
        )

    referer = request.META.get("HTTP_REFERER")
    if referer:
        return redirect(referer)
    return redirect(f"/?vista=mes&fecha={lunes_val.isoformat()}")


def calendario_semanal_view(request):
    """Vista semanal horaria del calendario con métricas de autobús para Pau (R3)."""
    from planificador_turnos.views import home

    req_copy = request.GET.copy()
    req_copy["vista"] = "semana"
    request.GET = req_copy
    return home(request)

