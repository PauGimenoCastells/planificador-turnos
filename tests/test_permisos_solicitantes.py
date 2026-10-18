from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import ConfiguracionTurno


@pytest.fixture
def usuarios(db):
    user_pau, _ = User.objects.get_or_create(username="pau", defaults={"is_superuser": True})
    user_pau.set_password("paupass123")
    user_pau.save()

    user_pol, _ = User.objects.get_or_create(username="pol", defaults={"is_superuser": False})
    user_pol.set_password("polpass123")
    user_pol.save()

    user_manolo, _ = User.objects.get_or_create(username="manolo", defaults={"is_superuser": False})
    user_manolo.set_password("manolopass123")
    user_manolo.save()

    config = ConfiguracionTurno.obtener_activa()
    config.fecha_base = date(2026, 10, 5)
    config.turno_inicial = "A"
    config.url_ical_uni = "https://example.com/test.ics"
    config.save()

    return {
        "pau": user_pau,
        "pol": user_pol,
        "manolo": user_manolo,
        "config": config,
    }


@pytest.mark.django_db
def test_r1_solicitante_fijado_en_vista_semanal_e_ignora_vista_mes(usuarios):
    """R1: Los usuarios solicitantes están forzados a la vista semanal y no ven el selector de mes."""
    client_pol = Client()
    client_pol.force_login(usuarios["pol"])

    # Acceso normal sin parámetros
    resp = client_pol.get("/")
    assert resp.status_code == 200
    assert resp.context["vista"] == "semana"
    assert resp.context["puede_gestionar"] is False
    assert "turnos/calendario_semanal.html" in [t.name for t in resp.templates if t.name]
    # No debe existir el enlace al selector de mes
    assert b'href="?vista=mes"' not in resp.content

    # Intento de forzar vista mes por query param
    resp_mes = client_pol.get("/?vista=mes")
    assert resp_mes.status_code == 200
    assert resp_mes.context["vista"] == "semana"
    assert "turnos/calendario.html" not in [t.name for t in resp_mes.templates if t.name]
    assert "turnos/calendario_semanal.html" in [t.name for t in resp_mes.templates if t.name]


@pytest.mark.django_db
def test_r1_gestor_pau_mantiene_acceso_a_vista_mes_y_semana(usuarios):
    """R1: Pau (gestor) puede alternar libremente entre mes y semana."""
    client_pau = Client()
    client_pau.force_login(usuarios["pau"])

    # Pau puede ver la vista mensual por defecto
    resp_mes = client_pau.get("/?vista=mes")
    assert resp_mes.status_code == 200
    assert resp_mes.context["vista"] == "mes"
    assert resp_mes.context["puede_gestionar"] is True
    assert "turnos/calendario.html" in [t.name for t in resp_mes.templates if t.name]
    assert b'href="?vista=semana"' in resp_mes.content

    # Pau en vista semanal ve el selector de mes
    resp_semana = client_pau.get("/?vista=semana")
    assert resp_semana.status_code == 200
    assert resp_semana.context["vista"] == "semana"
    assert b'href="?vista=mes"' in resp_semana.content


@pytest.mark.django_db
def test_r2_solicitante_no_ve_botones_de_calendario_uni(usuarios):
    """R2: No debe aparecer el botón de Calendario Uni ni el enlace de gestionar iCal en la barra lateral."""
    client_pol = Client()
    client_pol.force_login(usuarios["pol"])

    resp = client_pol.get("/")
    assert resp.status_code == 200
    assert b'href="/turnos/calendario-uni/"' not in resp.content
    assert "Calendario Uni" not in resp.content.decode("utf-8")
    assert "Gestionar feed iCal" not in resp.content.decode("utf-8")

    # Pau sí los ve en la vista semanal
    client_pau = Client()
    client_pau.force_login(usuarios["pau"])
    resp_pau = client_pau.get("/?vista=semana")
    assert resp_pau.status_code == 200
    assert b'href="/turnos/calendario-uni/"' in resp_pau.content
    assert "Calendario Uni" in resp_pau.content.decode("utf-8")
    assert "Gestionar feed iCal" in resp_pau.content.decode("utf-8")


@pytest.mark.django_db
def test_r3_solicitante_no_tiene_interaccion_ni_modal_de_reubicacion_de_clases(
    usuarios, monkeypatch
):
    """R3: En solicitantes, las clases universitarias no tienen cursor interactivo ni modal de reubicación."""

    # Mock de eventos de semana con una clase
    eventos_fake = [
        {
            "fecha": date(2026, 10, 19),
            "dia_nombre": "Lunes",
            "codigo_turno": "A",
            "bloques": [
                {
                    "tipo": "clase",
                    "id": "clase-fisica-1",
                    "titulo": "Física Cuántica",
                    "hora_inicio_str": "16:00",
                    "hora_fin_str": "18:00",
                    "top_px": 500,
                    "height_px": 100,
                    "tiene_solapamiento": False,
                    "reubicada": False,
                    "uid_evento": "clase-fisica-1",
                    "fecha_original": date(2026, 10, 19),
                    "hora_inicio_original_str": "16:00",
                }
            ],
        }
    ]
    monkeypatch.setattr(
        "planificador_turnos.views.obtener_eventos_semana",
        lambda **kwargs: eventos_fake,
    )

    client_pol = Client()
    client_pol.force_login(usuarios["pol"])

    resp = client_pol.get("/")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Debe ver la clase, pero sin onclick ni modal
    assert "Física Cuántica" in html
    assert 'onclick="abrirModalReubicacion(this)"' not in html
    assert 'data-clase-bloque="true"' not in html
    assert 'id="modal-reubicar"' not in html
    assert "abrirModalReubicacion" not in html

    # Pau sí debe tener el onclick y el modal
    client_pau = Client()
    client_pau.force_login(usuarios["pau"])
    resp_pau = client_pau.get("/?vista=semana")
    html_pau = resp_pau.content.decode("utf-8")
    assert "Física Cuántica" in html_pau
    assert 'onclick="abrirModalReubicacion(this)"' in html_pau
    assert 'id="modal-reubicar"' in html_pau


def test_e2e_solicitante_pantalla(live_server, db):
    """Verifica con Playwright el login como solicitante pol y captura la interfaz sin controles de mes ni ical."""
    from pathlib import Path

    from playwright.sync_api import sync_playwright

    user_pol, _ = User.objects.get_or_create(username="pol", defaults={"is_superuser": False})
    user_pol.set_password("polpass123")
    user_pol.save()

    config = ConfiguracionTurno.obtener_activa()
    config.fecha_base = date(2026, 10, 5)
    config.turno_inicial = "A"
    config.save()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Inicio de sesión como pol
        page.goto(f"{live_server.url}/login/")
        page.fill('input[name="username"]', "pol")
        page.fill('input[name="password"]', "polpass123")
        page.click('button[type="submit"]')

        # Esperar carga del calendario semanal
        page.wait_for_selector("text=Vista Semanal")

        # Comprobar ausencia de botones restringidos
        assert page.locator('text="Calendario Uni"').count() == 0
        assert page.locator('a[href*="vista=mes"]').count() == 0
        assert page.locator('text="Gestionar feed iCal"').count() == 0

        # Guardar captura de evidencia
        ruta_img = Path(
            "../../.runtime/006-restricciones-usuarios-solicitantes/solicitante.png"
        ).resolve()
        ruta_img.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(ruta_img), full_page=True)

        browser.close()
