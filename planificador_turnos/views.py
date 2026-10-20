import calendar
from datetime import date, timedelta

from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from turnos.models import ConfiguracionTurno
from turnos.rotacion import (
    HORARIOS_TURNOS,
    obtener_eventos_semana,
    obtener_semanas_calendario,
)
from turnos.views import usuario_puede_gestionar

MESES_ES = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


def home(request):
    """Vista de inicio para la aplicación con soporte para vista mensual y semanal horaria."""
    context = {}
    if request.user.is_authenticated:
        from turnos.views import purgar_o_caducar_citas_vencidas

        purgar_o_caducar_citas_vencidas()

        config = ConfiguracionTurno.obtener_activa()
        puede_gestionar = usuario_puede_gestionar(request.user)
        puede_configurar = puede_gestionar

        if puede_gestionar:
            vista = request.GET.get("vista", "mes").lower()
            if vista not in ("mes", "semana"):
                vista = "mes"
        else:
            vista = "semana"

        try:
            offset = int(request.GET.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0

        fecha_hoy = date.today()

        # Determinar fecha de referencia
        fecha_param = request.GET.get("fecha")
        if fecha_param:
            try:
                fecha_referencia = date.fromisoformat(fecha_param)
            except ValueError:
                fecha_referencia = fecha_hoy + timedelta(weeks=offset)
        else:
            fecha_referencia = fecha_hoy + timedelta(weeks=offset)

        # Lunes de la semana seleccionada
        lunes_semana = fecha_referencia - timedelta(days=fecha_referencia.weekday())
        domingo_semana = lunes_semana + timedelta(days=6)

        # Semanas de vista mensual
        semanas_mes = obtener_semanas_calendario(fecha_referencia, config=config)

        # Días y bloques de vista semanal horaria
        dias_semana_horaria = obtener_eventos_semana(
            fecha_lunes=lunes_semana, config=config, usuario=request.user
        )

        # Métricas de aprovechamiento de autobús para Pau y administradores (R2, R3)
        metricas_bus = None
        if puede_gestionar:
            from turnos.rotacion import calcular_metricas_autobus

            metricas_bus = calcular_metricas_autobus(dias_semana_horaria)

        # Citas pendientes de confirmación para Pau y Admin (R4)
        citas_pendientes = []
        if puede_gestionar:
            try:
                from turnos.models import Cita

                citas_pendientes = list(
                    Cita.objects.filter(estado="solicitada")
                    .select_related("solicitante")
                    .order_by("fecha", "hora_inicio")
                )
            except Exception:  # noqa: BLE001
                citas_pendientes = []

        # Contraofertas pendientes de respuesta para el usuario solicitante (R4)
        mis_contraofertas = []
        if request.user.is_authenticated:
            try:
                from turnos.models import Cita

                mis_contraofertas = list(
                    Cita.objects.filter(solicitante=request.user, estado="contraoferta").order_by(
                        "fecha", "hora_inicio"
                    )
                )
            except Exception:  # noqa: BLE001
                mis_contraofertas = []

        # Leyenda de usuarios y colores asignados (R1)
        leyenda_usuarios = [
            {"nombre": "Pol", "usuario": "pol", "color": "#10B981"},
            {"nombre": "Manolo", "usuario": "manolo", "color": "#F59E0B"},
            {"nombre": "Paco", "usuario": "paco", "color": "#8B5CF6"},
            {"nombre": "Random", "usuario": "random", "color": "#EC4899"},
        ]

        # Horas del eje vertical (00:00 a 23:00)
        horas_dia = [f"{h:02d}:00" for h in range(24)]

        # Mini-calendario para el sidebar de la vista semanal
        cal = calendar.Calendar(firstweekday=0)
        mini_ano = lunes_semana.year
        mini_mes = lunes_semana.month
        semanas_mini_raw = cal.monthdatescalendar(mini_ano, mini_mes)
        semanas_mini = []
        for sem in semanas_mini_raw:
            dias_mini = []
            for d in sem:
                dias_mini.append(
                    {
                        "numero": d.day,
                        "fecha_iso": d.isoformat(),
                        "mismo_mes": d.month == mini_mes,
                        "es_hoy": d == fecha_hoy,
                        "en_semana": lunes_semana <= d <= domingo_semana,
                    }
                )
            semanas_mini.append(dias_mini)

        # Enlaces de mes anterior y siguiente para mini-calendario
        if mini_mes == 1:
            mini_prev_fecha = date(mini_ano - 1, 12, 1).isoformat()
        else:
            mini_prev_fecha = date(mini_ano, mini_mes - 1, 1).isoformat()

        if mini_mes == 12:
            mini_next_fecha = date(mini_ano + 1, 1, 1).isoformat()
        else:
            mini_next_fecha = date(mini_ano, mini_mes + 1, 1).isoformat()

        # Navegación mensual natural (R1)
        if fecha_referencia.month == 1:
            fecha_mes_anterior = date(fecha_referencia.year - 1, 12, 1).isoformat()
        else:
            fecha_mes_anterior = date(fecha_referencia.year, fecha_referencia.month - 1, 1).isoformat()

        if fecha_referencia.month == 12:
            fecha_mes_siguiente = date(fecha_referencia.year + 1, 1, 1).isoformat()
        else:
            fecha_mes_siguiente = date(fecha_referencia.year, fecha_referencia.month + 1, 1).isoformat()

        if vista == "mes":
            titulo_mes_ano = f"{MESES_ES[fecha_referencia.month]} {fecha_referencia.year}"
        else:
            titulo_mes_ano = f"{MESES_ES[lunes_semana.month]} {lunes_semana.year}"

        excepcion_turno_semana = None
        if puede_gestionar:
            try:
                from turnos.models import ExcepcionTurnoSemana

                exc = ExcepcionTurnoSemana.objects.filter(lunes_semana=lunes_semana).first()
                if exc:
                    excepcion_turno_semana = exc.turno
            except Exception:  # noqa: BLE001, S110
                pass

        context.update(
            {
                "config": config,
                "puede_configurar": puede_configurar,
                "puede_gestionar": puede_gestionar,
                "vista": vista,
                "offset": offset,
                "offset_prev": offset - 1,
                "offset_next": offset + 1,
                "offset_plus_3": offset + 3,
                "offset_minus_3": offset - 3,
                "fecha_referencia": fecha_referencia,
                "fecha_hoy": fecha_hoy,
                "fecha_hoy_iso": fecha_hoy.isoformat(),
                "lunes_semana": lunes_semana,
                "excepcion_turno_semana": excepcion_turno_semana,
                "domingo_semana": domingo_semana,
                "fecha_semana_anterior": (lunes_semana - timedelta(days=7)).isoformat(),
                "fecha_semana_siguiente": (lunes_semana + timedelta(days=7)).isoformat(),
                "fecha_mes_anterior": fecha_mes_anterior,
                "fecha_mes_siguiente": fecha_mes_siguiente,
                "titulo_mes_ano": titulo_mes_ano,
                "mini_prev_fecha": mini_prev_fecha,
                "mini_next_fecha": mini_next_fecha,
                "semanas": semanas_mes,
                "dias_semana": dias_semana_horaria,
                "horas_dia": horas_dia,
                "semanas_mini": semanas_mini,
                "horarios_turnos": HORARIOS_TURNOS,
                "citas_pendientes": citas_pendientes,
                "mis_contraofertas": mis_contraofertas,
                "leyenda_usuarios": leyenda_usuarios,
                "metricas_bus": metricas_bus,
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


def health_check_view(request):
    """Endpoint de diagnóstico y verificación de salud de SQLite y la aplicación (R1)."""
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse(
            {
                "status": "ok",
                "db": True,
                "timestamp": timezone.now().isoformat(),
            },
            status=200,
        )
    except Exception as e:  # noqa: BLE001
        return JsonResponse(
            {
                "status": "error",
                "db": False,
                "error": str(e),
                "timestamp": timezone.now().isoformat(),
            },
            status=500,
        )

