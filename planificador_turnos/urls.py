from django.contrib.admin import site as admin_site
from django.urls import path

from planificador_turnos.views import health_check_view, home, login_view, logout_view
from turnos.views import (
    alternar_festivo_view,
    calendario_semanal_view,
    cambiar_turno_semana_view,
    cancelar_cita_view,
    configurar_calendario_uni,
    configurar_turnos,
    confirmar_cita_view,
    contraofertar_cita_view,
    gestion_usuarios_view,
    guardar_actividades_bus_view,
    rechazar_cita_view,
    responder_contraoferta_view,
    restablecer_clase_view,
    reubicar_clase_view,
    solicitar_cita_view,
)

urlpatterns = [
    path("admin/", admin_site.urls),
    path("health/", health_check_view, name="health_check"),
    path("", home, name="home"),
    path("turnos/semanal/", calendario_semanal_view, name="calendario_semanal"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("configurar-turnos/", configurar_turnos, name="configurar_turnos_root"),
    path("turnos/configurar/", configurar_turnos, name="configurar_turnos"),
    path("turnos/calendario-uni/", configurar_calendario_uni, name="configurar_calendario_uni"),
    path("turnos/alternar-festivo/", alternar_festivo_view, name="alternar_festivo"),
    path("turnos/reubicar-clase/", reubicar_clase_view, name="reubicar_clase"),
    path("turnos/restablecer-clase/", restablecer_clase_view, name="restablecer_clase"),
    path("turnos/solicitar-cita/", solicitar_cita_view, name="solicitar_cita"),
    path("turnos/confirmar-cita/", confirmar_cita_view, name="confirmar_cita"),
    path("turnos/rechazar-cita/", rechazar_cita_view, name="rechazar_cita"),
    path("turnos/cancelar-cita/", cancelar_cita_view, name="cancelar_cita"),
    path("turnos/contraofertar-cita/", contraofertar_cita_view, name="contraofertar_cita"),
    path(
        "turnos/responder-contraoferta/", responder_contraoferta_view, name="responder_contraoferta"
    ),
    path(
        "turnos/guardar-actividades-bus/",
        guardar_actividades_bus_view,
        name="guardar_actividades_bus",
    ),
    path(
        "turnos/cambiar-turno-semana/",
        cambiar_turno_semana_view,
        name="cambiar_turno_semana",
    ),
    path("turnos/usuarios/", gestion_usuarios_view, name="gestion_usuarios"),
]

