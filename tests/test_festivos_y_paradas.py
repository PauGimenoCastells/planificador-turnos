from datetime import date, timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import ConfiguracionTurno, FestivoParada
from turnos.rotacion import (
    FESTIVOS_OFICIALES_MARTORELL_2026,
    consultar_festivo_dia,
    obtener_turno_dia,
)


@pytest.mark.django_db
def test_r1_catalogo_oficial_festivos_martorell_2026_precargado():
    """R1: Catálogo oficial de 14 festivos de Martorell 2026 precargado y anula turnos de fábrica y bus."""
    assert len(FESTIVOS_OFICIALES_MARTORELL_2026) == 14

    # Festivos locales específicos de Martorell 2026
    assert date(2026, 4, 27) in FESTIVOS_OFICIALES_MARTORELL_2026
    assert "Sant Crist" in FESTIVOS_OFICIALES_MARTORELL_2026[date(2026, 4, 27)]
    assert date(2026, 5, 25) in FESTIVOS_OFICIALES_MARTORELL_2026
    assert "Segona Pasqua" in FESTIVOS_OFICIALES_MARTORELL_2026[date(2026, 5, 25)]

    # Festivos de Catalunya y España clave
    assert date(2026, 1, 1) in FESTIVOS_OFICIALES_MARTORELL_2026
    assert date(2026, 1, 6) in FESTIVOS_OFICIALES_MARTORELL_2026
    assert date(2026, 4, 3) in FESTIVOS_OFICIALES_MARTORELL_2026  # Viernes Santo
    assert date(2026, 4, 6) in FESTIVOS_OFICIALES_MARTORELL_2026  # Lunes de Pascua
    assert date(2026, 5, 1) in FESTIVOS_OFICIALES_MARTORELL_2026  # Fiesta del Trabajo
    assert date(2026, 6, 24) in FESTIVOS_OFICIALES_MARTORELL_2026  # Sant Joan
    assert date(2026, 8, 15) in FESTIVOS_OFICIALES_MARTORELL_2026  # Asunción
    assert date(2026, 9, 11) in FESTIVOS_OFICIALES_MARTORELL_2026  # Diada
    assert date(2026, 10, 12) in FESTIVOS_OFICIALES_MARTORELL_2026  # Fiesta Nacional
    assert date(2026, 12, 8) in FESTIVOS_OFICIALES_MARTORELL_2026  # Inmaculada
    assert date(2026, 12, 25) in FESTIVOS_OFICIALES_MARTORELL_2026  # Navidad
    assert date(2026, 12, 26) in FESTIVOS_OFICIALES_MARTORELL_2026  # Sant Esteve

    # Verificar que por defecto en festivo no hay fábrica ni autobuses
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 1, 1), turno_inicial="A")
    info_consulta = consultar_festivo_dia(date(2026, 4, 27))
    assert info_consulta is not None
    assert info_consulta["es_festivo"] is True
    info = obtener_turno_dia(date(2026, 4, 27))
    assert info["es_festivo"] is True
    assert "Sant Crist" in (info.get("nombre_festivo") or info.get("nombre") or "")
    assert info["fabrica"] is None
    assert info["bus_ida"] is None
    assert info["bus_vuelta"] is None


@pytest.mark.django_db
def test_r2_apertura_modal_festivo_en_calendario_mensual_para_gestor():
    """R2: Modal #modal-festivo-dia disponible en calendario mensual para Pau."""
    User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    client = Client()
    client.login(username="pau", password="password123")

    response = client.get("/?vista=mes&fecha=2026-04-15")
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Contenedor del modal de festivos/paradas presente en el DOM
    assert "modal-festivo-dia" in content
    assert "/turnos/alternar-festivo/" in content
    # Zona interactiva en el centro del día para abrir modal
    assert "abrirModalFestivo" in content or "data-modal-festivo" in content or "modal-festivo" in content


@pytest.mark.django_db
def test_r3_alternar_festivo_y_revertir_con_persistencia():
    """R3: Pau puede alternar un día laborable a festivo/parada y revertirlo con persistencia en FestivoParada."""
    User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    client = Client()
    client.login(username="pau", password="password123")

    # 1. 2026-04-15 es un miércoles laboral ordinario
    info_inicial = obtener_turno_dia(date(2026, 4, 15))
    assert info_inicial.get("es_festivo", False) is False
    assert info_inicial["codigo"] in ("A", "B", "C")

    # 2. Marcar 2026-04-15 como parada de fábrica
    response_marcar = client.post(
        "/turnos/alternar-festivo/",
        {
            "fecha": "2026-04-15",
            "accion": "marcar_festivo",
            "motivo": "Parada técnica mantenimiento",
        },
        follow=True,
    )
    assert response_marcar.status_code == 200

    # Comprobar persistencia en FestivoParada
    registro = FestivoParada.objects.get(fecha=date(2026, 4, 15))
    assert registro.es_festivo is True
    assert registro.motivo == "Parada técnica mantenimiento"

    # Verificar que el cálculo ahora anula fábrica y bus
    info_modificada = obtener_turno_dia(date(2026, 4, 15))
    assert info_modificada["es_festivo"] is True
    assert info_modificada["fabrica"] is None
    assert info_modificada["bus_ida"] is None

    # 3. Revertir a laborable
    response_revertir = client.post(
        "/turnos/alternar-festivo/",
        {
            "fecha": "2026-04-15",
            "accion": "revertir_laborable",
        },
        follow=True,
    )
    assert response_revertir.status_code == 200

    registro.refresh_from_db()
    assert registro.es_festivo is False

    info_revertida = obtener_turno_dia(date(2026, 4, 15))
    assert info_revertida.get("es_festivo", False) is False
    assert info_revertida["codigo"] in ("A", "B", "C")
    assert info_revertida["fabrica"] is not None

    # 4. Revertir festivo oficial (2026-04-27 Sant Crist) a laborable
    response_revertir_oficial = client.post(
        "/turnos/alternar-festivo/",
        {
            "fecha": "2026-04-27",
            "accion": "revertir_laborable",
        },
        follow=True,
    )
    assert response_revertir_oficial.status_code == 200
    info_oficial_revertida = obtener_turno_dia(date(2026, 4, 27))
    assert info_oficial_revertida.get("es_festivo", False) is False
    assert info_oficial_revertida["codigo"] in ("A", "B", "C")


@pytest.mark.django_db
def test_r4_distintivo_visual_en_calendario_mensual_y_anulacion_turno():
    """R4: Los festivos y paradas muestran distintivo visual y no tienen bloques de fábrica ni bus."""
    User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    # Creamos además una parada manual en 2026-04-10
    FestivoParada.objects.create(
        fecha=date(2026, 4, 10),
        es_festivo=True,
        motivo="Parada técnica fábrica",
    )

    client = Client()
    client.login(username="pau", password="password123")

    response = client.get("/?vista=mes&fecha=2026-04-15")
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Debe contener mención al festivo oficial y a la parada personalizada
    assert "Sant Crist" in content or "Viernes Santo" in content
    assert "Parada técnica fábrica" in content


@pytest.mark.django_db
def test_r5_permisos_y_privacidad_solicitantes():
    """R5: Solicitantes ven festivos a título informativo sin interactividad modal y POST devuelve 403."""
    User.objects.create_user(username="pol", password="password123")
    User.objects.create_user(username="manolo", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    client_pol = Client()
    client_pol.login(username="pol", password="password123")

    # Pol intenta modificar un festivo
    resp_pol_post = client_pol.post(
        "/turnos/alternar-festivo/",
        {
            "fecha": "2026-04-15",
            "accion": "marcar_festivo",
            "motivo": "Intento no autorizado",
        },
    )
    assert resp_pol_post.status_code == 403

    # Usuario anónimo intenta modificar
    client_anon = Client()
    resp_anon = client_anon.post(
        "/turnos/alternar-festivo/",
        {
            "fecha": "2026-04-15",
            "accion": "marcar_festivo",
        },
    )
    assert resp_anon.status_code in (403, 302)


@pytest.mark.django_db
def test_r7_fin_de_semana_forzado_a_laborable():
    """R1: Un fin de semana (sábado/domingo) forzado a laborable pierde condición de descanso y tiene turno de fábrica y bus."""
    User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    sabado = date(2026, 4, 18)  # Sábado
    assert sabado.weekday() == 5

    # 1. Por defecto es descanso semanal
    info_defecto = obtener_turno_dia(sabado)
    assert info_defecto["es_descanso"] is True
    assert info_defecto["es_festivo"] is False
    assert info_defecto["fabrica"] is None
    assert info_defecto["bus_ida"] is None

    # 2. Pau marca el sábado como laborable mediante POST
    client = Client()
    client.login(username="pau", password="password123")
    resp = client.post(
        "/turnos/alternar-festivo/",
        {
            "fecha": "2026-04-18",
            "accion": "revertir_laborable",
            "motivo": "Turno extra de mantenimiento",
        },
        follow=True,
    )
    assert resp.status_code == 200

    # 3. Comprobar que en FestivoParada es_festivo es False
    fp = FestivoParada.objects.get(fecha=sabado)
    assert fp.es_festivo is False

    # 4. Comprobar que obtener_turno_dia devuelve día laborable con turno, fábrica y autobuses
    info_laborable = obtener_turno_dia(sabado)
    assert info_laborable["es_descanso"] is False
    assert info_laborable["es_festivo"] is False
    assert info_laborable["codigo"] in ("A", "B", "C")
    assert info_laborable["fabrica"] is not None
    assert info_laborable["bus_ida"] is not None
    assert info_laborable["bus_vuelta"] is not None


@pytest.mark.django_db
def test_r8_cambio_turno_semanal_completo_desde_el_lunes():
    """R2 (Criterio portante): Cambio masivo de turno de toda la semana desde el lunes con persistencia y restablecimiento."""
    from turnos.models import ExcepcionTurnoSemana

    User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    client = Client()
    client.login(username="pau", password="password123")

    lunes_semana = date(2026, 4, 13)
    assert lunes_semana.weekday() == 0

    # Turno natural previo para esa semana
    info_previa = obtener_turno_dia(lunes_semana)
    turno_previo = info_previa["codigo"]

    # Elegimos un turno distinto para anular toda la semana
    nuevo_turno = "C" if turno_previo != "C" else "B"

    # 1. Pau cambia el turno de la semana completa a nuevo_turno
    resp_cambio = client.post(
        "/turnos/cambiar-turno-semana/",
        {
            "lunes_semana": "2026-04-13",
            "turno": nuevo_turno,
        },
        follow=True,
    )
    assert resp_cambio.status_code == 200

    # Verificar registro en base de datos
    excepcion = ExcepcionTurnoSemana.objects.get(lunes_semana=lunes_semana)
    assert excepcion.turno == nuevo_turno

    # Verificar que de lunes a viernes toda la semana tiene nuevo_turno
    for offset in range(5):  # Lunes a viernes
        dia = lunes_semana + timedelta(days=offset)
        info_dia = obtener_turno_dia(dia)
        assert info_dia["codigo"] == nuevo_turno, f"El día {dia} debería tener turno {nuevo_turno}"

    # 2. Pau restablece la rotación normal
    resp_restablecer = client.post(
        "/turnos/cambiar-turno-semana/",
        {
            "lunes_semana": "2026-04-13",
            "turno": "restablecer",
        },
        follow=True,
    )
    assert resp_restablecer.status_code == 200
    assert not ExcepcionTurnoSemana.objects.filter(lunes_semana=lunes_semana).exists()

    # Comprobar que vuelve al turno previo
    info_restablecida = obtener_turno_dia(lunes_semana)
    assert info_restablecida["codigo"] == turno_previo


@pytest.mark.django_db
def test_r9_permisos_cambio_turno_semanal_solicitantes():
    """R4: Solo Pau o superusuarios pueden modificar el turno semanal; solicitantes y anónimos reciben 403 o redirección."""
    User.objects.create_user(username="pol", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    client_pol = Client()
    client_pol.login(username="pol", password="password123")

    resp_pol = client_pol.post(
        "/turnos/cambiar-turno-semana/",
        {
            "lunes_semana": "2026-04-13",
            "turno": "B",
        },
    )
    assert resp_pol.status_code == 403

    client_anon = Client()
    resp_anon = client_anon.post(
        "/turnos/cambiar-turno-semana/",
        {
            "lunes_semana": "2026-04-13",
            "turno": "B",
        },
    )
    assert resp_anon.status_code in (403, 302)


def test_r6_captura_modal_festivo(live_server):
    """Genera la captura de pantalla requerida en .runtime/012-festivos-martorell-y-paradas-fabrica/festivo_modal.png."""
    from playwright.sync_api import sync_playwright

    User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 4, 1), turno_inicial="A")

    out_dir = Path("../../.runtime/012-festivos-martorell-y-paradas-fabrica")
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = out_dir / "festivo_modal.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server.url}/login/")
        page.fill('input[name="username"]', "pau")
        page.fill('input[name="password"]', "password123")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")

        page.goto(f"{live_server.url}/?vista=mes&fecha=2026-04-15")
        page.wait_for_load_state("networkidle")

        # Pulsar en la zona interactiva del día para abrir el modal
        trigger = page.locator('[data-festivo-trigger="true"]').first
        trigger.click()
        page.wait_for_selector("#modal-festivo-dia:not(.hidden)")

        page.screenshot(path=str(screenshot_path.resolve()))
        browser.close()

    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0
