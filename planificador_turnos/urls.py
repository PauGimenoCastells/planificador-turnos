from django.contrib import admin
from django.urls import path

from planificador_turnos.views import home, login_view, logout_view
from turnos.views import (
    configurar_calendario_uni,
    configurar_turnos,
    restablecer_clase_view,
    reubicar_clase_view,
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
]
