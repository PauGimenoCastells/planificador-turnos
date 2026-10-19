from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import OperationalError
from django.test import Client

from turnos.models import ActividadAutobus, ConfiguracionTurno


@pytest.fixture
def datos_test(db):
    user_pau, _ = User.objects.get_or_create(username="pau", defaults={"is_superuser": True})
    user_pau.set_password("paupass123")
    user_pau.save()

    user_admin, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
    user_admin.set_password("adminpass123")
    user_admin.save()

    user_pol, _ = User.objects.get_or_create(username="pol", defaults={"is_superuser": False})
    user_pol.set_password("polpass123")
    user_pol.save()

    user_manolo, _ = User.objects.get_or_create(username="manolo", defaults={"is_superuser": False})
    user_manolo.set_password("manolopass123")
    user_manolo.save()

    user_paco, _ = User.objects.get_or_create(username="paco", defaults={"is_superuser": False})
    user_paco.set_password("pacopass123")
    user_paco.save()

    user_random, _ = User.objects.get_or_create(username="random", defaults={"is_superuser": False})
    user_random.set_password("randompass123")
    user_random.save()

    config = ConfiguracionTurno.obtener_activa()
    config.fecha_base = date(2026, 10, 12)  # Lunes Turno A
    config.turno_inicial = "A"
    config.save()

    return {
        "pau": user_pau,
        "admin": user_admin,
        "pol": user_pol,
        "manolo": user_manolo,
        "paco": user_paco,
        "random": user_random,
        "config": config,
    }


# ==============================================================================
# R1: Endpoint /health/ responde HTTP 200 y status 500 si la base de datos falla
# ==============================================================================
@pytest.mark.django_db
def test_r1_endpoint_health_200_ok():
    """R1: /health/ responde JSON {"status": "ok", "db": true, ...} con HTTP 200 en estado normal."""
    client = Client()
    resp = client.get("/health/")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("db") is True
    assert "timestamp" in data


@pytest.mark.django_db
def test_r1_endpoint_health_500_db_error():
    """R1: /health/ responde JSON {"status": "error", "db": false} con HTTP 500 si la base de datos falla."""
    client = Client()
    with patch("django.db.connection.ensure_connection", side_effect=OperationalError("DB connection error")):
        resp = client.get("/health/")
        assert resp.status_code == 500
        data = resp.json()
        assert data.get("status") == "error"
        assert data.get("db") is False


# ==============================================================================
# R2: Cómputo exacto de tiempo total y desglose por actividad (Criterio Portante)
# ==============================================================================
@pytest.mark.django_db
def test_r2_computo_metricas_autobus_portante(datos_test):
    """
    R2 (Criterio Portante): Cómputo exacto de tiempo total y desglose por actividad
    (siesta, lectura, reflexion, videojuegos, videos) en turnos/rotacion.py
    para los trayectos de autobús completados en la semana visible con actividades guardadas.
    """
    from turnos.rotacion import calcular_metricas_autobus, obtener_eventos_semana

    fecha_pasada = date.today() - timedelta(days=7)
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())
    martes_pasado = lunes_pasado + timedelta(days=1)

    # Lunes Turno A: bus_ida (45 min) con lectura y siesta
    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_ida",
        actividades=["lectura", "siesta"],
    )
    # Lunes Turno A: bus_vuelta (90 min) con lectura y reflexion
    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_vuelta",
        actividades=["lectura", "reflexion"],
    )
    # Martes Turno A: bus_ida (45 min) con videojuegos
    ActividadAutobus.objects.create(
        fecha=martes_pasado,
        tipo_bus="bus_ida",
        actividades=["videojuegos"],
    )

    dias_semana = obtener_eventos_semana(
        fecha_lunes=lunes_pasado, config=datos_test["config"], usuario=datos_test["pau"]
    )

    metricas = calcular_metricas_autobus(dias_semana)

    # Duración total de trayectos completados con actividad: 45 + 90 + 45 = 180 min (3h)
    assert metricas["total_minutos"] == 180, "R-02 Portante: total_minutos debe sumar 180 minutos"
    assert metricas["total_formateado"] == "3h"
    assert metricas["total_trayectos"] == 3

    # Desglose por actividad con reparto equitativo (P-20261019-f95ab3e6):
    # Lunes bus_ida (45m entre lectura y siesta) -> 22.5m cada una
    # Lunes bus_vuelta (90m entre lectura y reflexion) -> 45m cada una
    # Martes bus_ida (45m con videojuegos) -> 45m
    # lectura: 22.5 + 45 = 67.5 min -> 68m (1h 8m)
    # siesta: 22.5 min -> 22m o 23m
    # reflexion: 45 min -> 45m
    # videojuegos: 45 min -> 45m
    # videos: 0 min -> 0m
    assert metricas["por_actividad"]["lectura"]["minutos"] == 68
    assert metricas["por_actividad"]["lectura"]["tiempo_formateado"] == "1h 8m"

    assert metricas["por_actividad"]["siesta"]["minutos"] in (22, 23)
    assert metricas["por_actividad"]["siesta"]["tiempo_formateado"] in ("22m", "23m")

    assert metricas["por_actividad"]["reflexion"]["minutos"] == 45
    assert metricas["por_actividad"]["reflexion"]["tiempo_formateado"] == "45m"

    assert metricas["por_actividad"]["videojuegos"]["minutos"] == 45
    assert metricas["por_actividad"]["videojuegos"]["tiempo_formateado"] == "45m"

    assert metricas["por_actividad"]["videos"]["minutos"] == 0
    assert metricas["por_actividad"]["videos"]["tiempo_formateado"] == "0m"


@pytest.mark.django_db
def test_reparto_equitativo_tiempo_actividades_bus(datos_test):
    """Verifica que si un trayecto tiene N actividades, la duración del trayecto se divide entre N."""
    from turnos.rotacion import calcular_metricas_autobus

    bloques_dia = [
        {
            "fecha": date(2026, 10, 19),
            "bloques": [
                {
                    "tipo": "bus_ida",
                    "minuto_inicio": 360,
                    "minuto_fin": 420,  # 60 minutos
                    "actividades": ["lectura", "reflexion"],
                },
                {
                    "tipo": "bus_vuelta",
                    "minuto_inicio": 800,
                    "minuto_fin": 860,  # 60 minutos
                    "actividades": ["siesta", "videojuegos", "videos"],
                },
            ],
        }
    ]

    metricas = calcular_metricas_autobus(bloques_dia)
    assert metricas["total_minutos"] == 120
    assert metricas["por_actividad"]["lectura"]["minutos"] == 30
    assert metricas["por_actividad"]["lectura"]["tiempo_formateado"] == "30m"
    assert metricas["por_actividad"]["reflexion"]["minutos"] == 30
    assert metricas["por_actividad"]["reflexion"]["tiempo_formateado"] == "30m"

    assert metricas["por_actividad"]["siesta"]["minutos"] == 20
    assert metricas["por_actividad"]["siesta"]["tiempo_formateado"] == "20m"
    assert metricas["por_actividad"]["videojuegos"]["minutos"] == 20
    assert metricas["por_actividad"]["videojuegos"]["tiempo_formateado"] == "20m"
    assert metricas["por_actividad"]["videos"]["minutos"] == 20
    assert metricas["por_actividad"]["videos"]["tiempo_formateado"] == "20m"


# ==============================================================================
# R3: Panel visual de aprovechamiento en la vista semanal
# ==============================================================================
@pytest.mark.django_db
def test_r3_panel_visual_metricas_vista_semanal_pau(datos_test):
    """
    R3: calendario_semanal.html muestra para Pau un panel visual de aprovechamiento
    con el tiempo total y badges con emojis por actividad.
    """
    client = Client()
    client.force_login(datos_test["pau"])

    fecha_pasada = date.today() - timedelta(days=7)
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())

    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_ida",
        actividades=["lectura", "siesta"],
    )

    resp = client.get(f"/turnos/semanal/?fecha={lunes_pasado.isoformat()}")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    assert 'id="panel-metricas-bus"' in html
    assert "Aprovechamiento en autobús" in html
    assert "45m" in html or "1h" in html
    assert "Lectura" in html
    assert "Siesta" in html


# ==============================================================================
# R4: Oscurecimiento del tono gris en la interfaz de autobús
# ==============================================================================
@pytest.mark.django_db
def test_r4_oscurecimiento_gris_interfaz_autobus(datos_test):
    """
    R4: El modal #modal-actividades-bus y los bloques de autobús con actividades
    adoptan escala de gris más oscura: bg-slate-200/95, border-slate-400,
    tarjetas interiores bg-slate-100, hover bg-slate-300.
    """
    client = Client()
    client.force_login(datos_test["pau"])

    fecha_pasada = date.today() - timedelta(days=7)
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())

    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_ida",
        actividades=["siesta"],
    )

    resp = client.get(f"/turnos/semanal/?fecha={lunes_pasado.isoformat()}")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Clases Tailwind oscurecidas requeridas
    assert "bg-slate-200" in html
    assert "border-slate-400" in html
    assert "bg-slate-100" in html
    assert "hover:bg-slate-300" in html or "hover:bg-slate-200" in html


# ==============================================================================
# R5: Privacidad y permisos: solicitantes sin acceso al panel ni actividades de Pau
# ==============================================================================
@pytest.mark.django_db
def test_r5_privacidad_solicitantes(datos_test):
    """
    R5: Los solicitantes (Pol, Manolo, Paco, Random) no tienen acceso a ver el panel
    de métricas de autobús ni las actividades personales de Pau.
    """
    client = Client()

    fecha_pasada = date.today() - timedelta(days=7)
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())

    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_ida",
        actividades=["lectura", "siesta"],
    )

    solicitantes = [datos_test["pol"], datos_test["manolo"], datos_test["paco"], datos_test["random"]]
    for usuario in solicitantes:
        client.force_login(usuario)
        resp = client.get(f"/turnos/semanal/?fecha={lunes_pasado.isoformat()}")
        assert resp.status_code == 200
        html = resp.content.decode("utf-8")

        # No debe ver el panel de métricas de autobús
        assert 'id="panel-metricas-bus"' not in html
        assert "Aprovechamiento en autobús" not in html
        # No debe ver el modal de actividades de autobús
        assert 'id="modal-actividades-bus"' not in html


def test_captura_metricas_bus_ui(live_server):
    """Genera la captura de pantalla requerida en .runtime/013-metricas-bus-y-salud-despliegue/metricas_bus.png."""
    from pathlib import Path

    from playwright.sync_api import sync_playwright

    user_pau, _ = User.objects.get_or_create(username="pau", defaults={"is_superuser": True})
    user_pau.set_password("paupass123")
    user_pau.save()

    fecha_pasada = date.today() - timedelta(days=7)
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())
    ConfiguracionTurno.objects.create(fecha_base=lunes_pasado, turno_inicial="A")

    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_ida",
        actividades=["lectura", "siesta"],
    )

    out_dirs = [
        Path(".runtime/013-metricas-bus-y-salud-despliegue"),
        Path("../../.runtime/013-metricas-bus-y-salud-despliegue"),
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{live_server.url}/login/")
        page.fill('input[name="username"]', "pau")
        page.fill('input[name="password"]', "paupass123")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")

        page.goto(f"{live_server.url}/?vista=semana&fecha={lunes_pasado.isoformat()}")
        page.wait_for_load_state("networkidle")

        # Abre el modal de autobús completado para ver el panel de métricas y el modal oscurecido
        bus_trigger = page.locator('[data-bus-bloque="true"]').first
        if bus_trigger.count() > 0:
            bus_trigger.click()
            page.wait_for_timeout(300)

        for d in out_dirs:
            shot_path = d / "metricas_bus.png"
            page.screenshot(path=str(shot_path.resolve()))
        browser.close()

    assert (out_dirs[0] / "metricas_bus.png").exists()
    assert (out_dirs[0] / "metricas_bus.png").stat().st_size > 0

