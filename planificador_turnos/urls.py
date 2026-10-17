from django.contrib import admin
from django.urls import path

from planificador_turnos.views import home, login_view, logout_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
]
