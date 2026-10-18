from django.contrib import admin
from django.urls import path

from planificador_turnos.views import home, login_view, logout_view
from turnos.views import (
    cancelar_cita_view,
    configurar_calendario_uni,
    configurar_turnos,
    confirmar_cita_view,
    contraofertar_cita_view,
    rechazar_cita_view,
    responder_contraoferta_view,
    restablecer_clase_view,
    reubicar_clase_view,
    solicitar_cita_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("turnos/configurar/", configurar_turnos, name="configurar_turnos"),
    path("turnos/calendario-uni/", configurar_calendario_uni, name="configurar_calendario_uni"),
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
]
