from datetime import date, time

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import ConfiguracionTurno
from turnos.rotacion import (
    COLORES_SOLICITANTES,
    obtener_color_solicitante,
    obtener_franjas_disponibles_semana,
)


@pytest.fixture
def usuarios_citas(db):
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
    config.fecha_base = date(2026, 10, 12)
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
# R1: Cálculo y franjas disponibles según el turno activo de Pau
# ==============================================================================
@pytest.mark.django_db
def test_r1_calculo_franjas_disponibles_turnos_y_fines_de_semana(usuarios_citas):
    """
    R1: Franjas disponibles base:
    - Turno A: 15:35 a 19:45
    - Turno B: 08:00 a 12:30
    - Turno C: 15:30 a 20:15
    - Fines de semana: 08:00 a 22:00
    Descontando turnos de fábrica, autobuses y clases universitarias.
    """
    config = usuarios_citas["config"]
    lunes = date(2026, 10, 12)  # Turno A

    # Semana 1: Turno A
    franjas_sem = obtener_franjas_disponibles_semana(lunes, config=config)
    franjas_lunes = franjas_sem[lunes]
    assert len(franjas_lunes) == 1
    assert franjas_lunes[0]["hora_inicio_str"] == "15:35"
    assert franjas_lunes[0]["hora_fin_str"] == "19:45"

    # Fin de semana (Sábado)
    sabado = date(2026, 10, 17)
    franjas_sabado = franjas_sem[sabado]
    assert len(franjas_sabado) == 1
    assert franjas_sabado[0]["hora_inicio_str"] == "08:00"
    assert franjas_sabado[0]["hora_fin_str"] == "22:00"

    # Bloque 2 (a partir del día 21): Turno C (lunes 2 Nov 2026)
    lunes_c = date(2026, 11, 2)
    franjas_sem_c = obtener_franjas_disponibles_semana(lunes_c, config=config)
    franjas_lunes_c = franjas_sem_c[lunes_c]
    assert len(franjas_lunes_c) == 1
    assert franjas_lunes_c[0]["hora_inicio_str"] == "15:30"
    assert franjas_lunes_c[0]["hora_fin_str"] == "20:15"

    # Bloque 3 (a partir del día 42): Turno B (lunes 23 Nov 2026)
    lunes_b = date(2026, 11, 23)
    franjas_sem_b = obtener_franjas_disponibles_semana(lunes_b, config=config)
    franjas_lunes_b = franjas_sem_b[lunes_b]
    assert len(franjas_lunes_b) == 1
    assert franjas_lunes_b[0]["hora_inicio_str"] == "08:00"
    assert franjas_lunes_b[0]["hora_fin_str"] == "12:30"


@pytest.mark.django_db
def test_r1_descuento_de_clases_universitarias_en_franja_disponible(usuarios_citas, monkeypatch):
    """
    R1: Turno A con clase de 16:00 a 17:00 produce franjas 15:35-16:00 y 17:00-19:45.
    """
    config = usuarios_citas["config"]
    lunes = date(2026, 10, 12)

    # Simular una clase universitaria de 16:00 a 17:00 el lunes
    clases_fake = [
        {
            "fecha": lunes,
            "tipo": "clase",
            "titulo": "Física",
            "hora_inicio_str": "16:00",
            "hora_fin_str": "17:00",
            "minuto_inicio": 16 * 60,
            "minuto_fin": 17 * 60,
            "es_hito": False,
        }
    ]
    franjas_sem = obtener_franjas_disponibles_semana(lunes, config=config, eventos_ical=clases_fake)
    franjas_lunes = franjas_sem[lunes]

    assert len(franjas_lunes) == 2
    assert franjas_lunes[0]["hora_inicio_str"] == "15:35"
    assert franjas_lunes[0]["hora_fin_str"] == "16:00"
    assert franjas_lunes[1]["hora_inicio_str"] == "17:00"
    assert franjas_lunes[1]["hora_fin_str"] == "19:45"


# ==============================================================================
# R2: Selección restringida y ventana emergente de solicitud (<= 250 chars)
# ==============================================================================
@pytest.mark.django_db
def test_r2_solicitar_cita_valida_correctamente_y_crea_cita(usuarios_citas):
    """
    R2: Usuario pol solicita cita dentro de franja disponible (16:30 a 17:30)
    con motivo válido (< 250 chars). Devuelve redirect y estado solicitada.
    """
    client = Client()
    client.force_login(usuarios_citas["pol"])

    data = {
        "fecha": "2026-10-13",
        "hora_inicio": "16:30",
        "hora_fin": "17:30",
        "motivo": "Dudas de fluidos tema 4",
    }
    resp = client.post("/turnos/solicitar-cita/", data=data)
    assert resp.status_code == 302

    from turnos.models import Cita

    cita = Cita.objects.filter(solicitante=usuarios_citas["pol"]).first()
    assert cita is not None
    assert cita.fecha == date(2026, 10, 13)
    assert cita.hora_inicio == time(16, 30)
    assert cita.hora_fin == time(17, 30)
    assert cita.motivo == "Dudas de fluidos tema 4"
    assert cita.estado == "solicitada"


@pytest.mark.django_db
def test_r2_rechaza_solicitud_con_motivo_mayor_a_250_caracteres(usuarios_citas):
    """
    R2 / R-05 Portante: El motivo no puede superar estrictamente 250 caracteres (error 400).
    """
    client = Client()
    client.force_login(usuarios_citas["pol"])

    motivo_260 = "X" * 260
    data = {
        "fecha": "2026-10-13",
        "hora_inicio": "16:30",
        "hora_fin": "17:30",
        "motivo": motivo_260,
    }
    resp = client.post("/turnos/solicitar-cita/", data=data)
    assert resp.status_code == 400
    assert "250" in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_r2_rechaza_solicitud_fuera_de_franjas_disponibles(usuarios_citas):
    """
    R2: Solicitar cita a las 10:00 (en fábrica durante Turno A) es rechazado con error 400.
    """
    client = Client()
    client.force_login(usuarios_citas["pol"])

    data = {
        "fecha": "2026-10-13",
        "hora_inicio": "10:00",
        "hora_fin": "11:00",
        "motivo": "Reunión durante turno de fábrica",
    }
    resp = client.post("/turnos/solicitar-cita/", data=data)
    assert resp.status_code == 400
    assert "disponible" in resp.content.decode("utf-8").lower()


# ==============================================================================
# R3: Persistencia, colores por solicitante y estado apagado/translúcido
# ==============================================================================
@pytest.mark.django_db
def test_r3_colores_asignados_por_solicitante():
    """
    R3: Paleta de colores fija por solicitante:
    - pol: #10B981
    - manolo: #F59E0B
    - paco: #8B5CF6
    - random: #EC4899
    """
    assert COLORES_SOLICITANTES["pol"] == "#10B981"
    assert COLORES_SOLICITANTES["manolo"] == "#F59E0B"
    assert COLORES_SOLICITANTES["paco"] == "#8B5CF6"
    assert COLORES_SOLICITANTES["random"] == "#EC4899"
    assert obtener_color_solicitante("pol") == "#10B981"
    assert obtener_color_solicitante("manolo") == "#F59E0B"
    assert obtener_color_solicitante("paco") == "#8B5CF6"
    assert obtener_color_solicitante("random") == "#EC4899"


@pytest.mark.django_db
def test_r3_cita_solicitada_se_dibuja_en_color_apagado_con_etiqueta_pendiente(usuarios_citas):
    """
    R3: Una cita con estado solicitada se renderiza en la cuadrícula semanal con
    su color correspondiente, estilo translúcido ("apagado") y etiqueta 'Pendiente'.
    """
    from turnos.models import Cita

    Cita.objects.create(
        solicitante=usuarios_citas["pol"],
        fecha=date(2026, 10, 13),
        hora_inicio=time(16, 30),
        hora_fin=time(17, 30),
        motivo="Dudas de fluidos tema 4",
        estado="solicitada",
    )

    client = Client()
    client.force_login(usuarios_citas["pol"])

    resp = client.get("/?vista=semana&fecha=2026-10-12")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    assert "#10B981" in html
    assert "Pendiente" in html
    assert "16:30" in html


# ==============================================================================
# R4: Aviso visible para Pau/Admin y confirmación con bloqueo definitivo
# ==============================================================================
@pytest.mark.django_db
def test_r4_pau_y_admin_ven_aviso_de_citas_pendientes_y_pueden_confirmar(usuarios_citas):
    """
    R4: Pau y Admin ven las solicitudes pendientes en su panel con botón Confirmar.
    Al confirmar, la cita pasa a 'confirmada', bloque sólido, y la franja queda bloqueada.
    """
    from turnos.models import Cita

    cita = Cita.objects.create(
        solicitante=usuarios_citas["pol"],
        fecha=date(2026, 10, 13),
        hora_inicio=time(16, 30),
        hora_fin=time(17, 30),
        motivo="Dudas de fluidos tema 4",
        estado="solicitada",
    )

    client_pau = Client()
    client_pau.force_login(usuarios_citas["pau"])

    # Pau visualiza el aviso de cita pendiente
    resp_pau = client_pau.get("/?vista=semana&fecha=2026-10-12")
    assert resp_pau.status_code == 200
    html_pau = resp_pau.content.decode("utf-8")
    assert "pol" in html_pau
    assert "Dudas de fluidos tema 4" in html_pau
    assert "Confirmar" in html_pau

    # Pau confirma la cita
    resp_confirm = client_pau.post("/turnos/confirmar-cita/", data={"cita_id": cita.id})
    assert resp_confirm.status_code == 302

    cita.refresh_from_db()
    assert cita.estado == "confirmada"

    # Ahora la franja 16:30-17:30 está bloqueada y no disponible para otro solicitante
    client_manolo = Client()
    client_manolo.force_login(usuarios_citas["manolo"])
    resp_manolo_solicitud = client_manolo.post(
        "/turnos/solicitar-cita/",
        data={
            "fecha": "2026-10-13",
            "hora_inicio": "16:30",
            "hora_fin": "17:30",
            "motivo": "Reunión solapada",
        },
    )
    assert resp_manolo_solicitud.status_code == 400


# ==============================================================================
# R5: Privacidad de motivos y horas no hábiles como 'No disponible'
# ==============================================================================
@pytest.mark.django_db
def test_r5_privacidad_companeros_no_ven_motivo_de_otros_ni_detalles_privados(usuarios_citas):
    """
    R5: Manolo visualiza la cuadrícula:
    - Las horas de fábrica/clases de Pau aparecen como 'No disponible'.
    - La cita confirmada de Pol muestra 'Pol' y su horario, pero NUNCA el motivo privado.
    """
    from turnos.models import Cita

    Cita.objects.create(
        solicitante=usuarios_citas["pol"],
        fecha=date(2026, 10, 13),
        hora_inicio=time(16, 30),
        hora_fin=time(17, 30),
        motivo="Motivo hiper confidencial de examen",
        estado="confirmada",
    )

    client_manolo = Client()
    client_manolo.force_login(usuarios_citas["manolo"])

    resp = client_manolo.get("/?vista=semana&fecha=2026-10-12")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Manolo ve que está ocupado por Pol en esa franja
    assert "pol" in html.lower()
    # Pero NO debe existir el motivo privado de Pol
    assert "Motivo hiper confidencial de examen" not in html
    # Las horas no hábiles aparecen como 'No disponible'
    assert "No disponible" in html


def test_e2e_citas_captura_pantalla(live_server, db):
    """Genera la captura de pantalla de evidencia en .runtime/007-disponibilidad-y-reservas-citas/citas.png."""
    from pathlib import Path

    from playwright.sync_api import sync_playwright

    from turnos.models import Cita, ConfiguracionTurno

    config = ConfiguracionTurno.obtener_activa()
    config.fecha_base = date(2026, 10, 12)
    config.turno_inicial = "A"
    config.save()

    user_pau, _ = User.objects.get_or_create(username="pau", defaults={"is_superuser": True})
    user_pau.set_password("paupass123")
    user_pau.save()

    user_pol, _ = User.objects.get_or_create(username="pol", defaults={"is_superuser": False})
    user_pol.set_password("polpass123")
    user_pol.save()

    # Cita pendiente de Pol
    Cita.objects.create(
        solicitante=user_pol,
        fecha=date(2026, 10, 13),
        hora_inicio=time(16, 30),
        hora_fin=time(17, 30),
        motivo="Dudas de fluidos tema 4",
        estado="solicitada",
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Login como pau
        page.goto(f"{live_server.url}/login/")
        page.fill('input[name="username"]', "pau")
        page.fill('input[name="password"]', "paupass123")
        page.click('button[type="submit"]')

        # Navegar a vista semanal de la semana de turno A
        page.goto(f"{live_server.url}/?vista=semana&fecha=2026-10-12")
        page.wait_for_selector("text=Vista Semanal")
        page.wait_for_selector("#panel-citas-pendientes")

        ruta_img = Path("../../.runtime/007-disponibilidad-y-reservas-citas/citas.png").resolve()
        ruta_img.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(ruta_img), full_page=True)

        browser.close()
