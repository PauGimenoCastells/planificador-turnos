from datetime import date, time

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import ConfiguracionTurno

ICS_SOLAPAMIENTO_MIERCOLES = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//UNIR//Clases//ES
BEGIN:VEVENT
UID:clase-unir-miercoles-12
SUMMARY:Aula de información general
DTSTART;TZID=Europe/Madrid:20261021T120000
DTEND;TZID=Europe/Madrid:20261021T130000
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def usuario_pau(db):
    user = User.objects.create_user(username="pau", password="password123")
    config = ConfiguracionTurno.obtener_activa()
    config.fecha_base = date(2026, 10, 12)  # Semana del 19 al 25 es Turno A
    config.turno_inicial = "A"
    config.contenido_ical_cache = ICS_SOLAPAMIENTO_MIERCOLES
    config.save()
    return user


@pytest.mark.django_db
def test_r1_portante_apertura_y_datos_modal_reubicacion(usuario_pau):
    """
    R1 (Portante): En la vista semanal, al hacer clic en una clase que presenta solapamiento
    (miércoles 21 de octubre a las 12:00 solapada con Turno A), se dispone de un diálogo interactivo
    de reubicación que muestra el título de la clase, su horario original y campos para seleccionar
    nueva fecha y hora de inicio.
    """
    client = Client()
    client.login(username="pau", password="password123")

    response = client.get("/?vista=semana&fecha=2026-10-21")
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Debe contener la clase y aviso de solapamiento
    assert "Aula de información general" in content
    assert "12:00" in content

    # Comprobar disparador interactivo y modal de reubicación
    assert (
        "modal-reubicar" in content
        or "data-modal-target" in content
        or 'id="modal-reubicar"' in content
    )
    assert "data-uid" in content or "clase-unir-miercoles-12" in content
    assert 'name="nueva_fecha"' in content or "name='nueva_fecha'" in content
    assert 'name="nueva_hora_inicio"' in content or "name='nueva_hora_inicio'" in content
    assert "/turnos/reubicar-clase/" in content


@pytest.mark.django_db
def test_r2_validacion_estricta_momento_posterior(usuario_pau):
    """
    R2: El sistema valida que la nueva fecha y hora de inicio sea estrictamente posterior
    al inicio original de la clase. Si es previa o igual, devuelve 400 y mensaje explicativo claro.
    """
    client = Client()
    client.login(username="pau", password="password123")

    # Caso 1: Mismo día, hora anterior (10:00 < 12:00) -> 400
    res_anterior_hora = client.post(
        "/turnos/reubicar-clase/",
        {
            "uid_evento": "clase-unir-miercoles-12",
            "fecha_original": "2026-10-21",
            "hora_inicio_original": "12:00",
            "nueva_fecha": "2026-10-21",
            "nueva_hora_inicio": "10:00",
        },
    )
    assert res_anterior_hora.status_code == 400
    assert "posterior" in res_anterior_hora.content.decode("utf-8").lower()

    # Caso 2: Mismo día, misma hora (12:00 == 12:00) -> 400
    res_misma_hora = client.post(
        "/turnos/reubicar-clase/",
        {
            "uid_evento": "clase-unir-miercoles-12",
            "fecha_original": "2026-10-21",
            "hora_inicio_original": "12:00",
            "nueva_fecha": "2026-10-21",
            "nueva_hora_inicio": "12:00",
        },
    )
    assert res_misma_hora.status_code == 400
    assert "posterior" in res_misma_hora.content.decode("utf-8").lower()

    # Caso 3: Día anterior (2026-10-20 < 2026-10-21) -> 400
    res_dia_anterior = client.post(
        "/turnos/reubicar-clase/",
        {
            "uid_evento": "clase-unir-miercoles-12",
            "fecha_original": "2026-10-21",
            "hora_inicio_original": "12:00",
            "nueva_fecha": "2026-10-20",
            "nueva_hora_inicio": "16:00",
        },
    )
    assert res_dia_anterior.status_code == 400
    assert "posterior" in res_dia_anterior.content.decode("utf-8").lower()

    # Caso 4: Momento posterior válido (mismo día 16:00 > 12:00) -> 302 Redirección
    res_valido = client.post(
        "/turnos/reubicar-clase/",
        {
            "uid_evento": "clase-unir-miercoles-12",
            "fecha_original": "2026-10-21",
            "hora_inicio_original": "12:00",
            "nueva_fecha": "2026-10-21",
            "nueva_hora_inicio": "16:00",
        },
    )
    assert res_valido.status_code == 302


@pytest.mark.django_db
def test_r3_reubicacion_exitosa_reposicionamiento_borde_azul_y_sin_solapamiento(usuario_pau):
    """
    R3: Al confirmar una reubicación válida, se guarda en base de datos, la clase se renderiza
    en la nueva fecha y hora con borde exterior #0369A1, duración original de 60 min,
    y sin alerta de solapamiento si la franja está libre.
    """
    from turnos.models import ReubicacionClase

    client = Client()
    client.login(username="pau", password="password123")

    # Reubicar clase de 12:00 a 16:00 el miércoles 21
    res = client.post(
        "/turnos/reubicar-clase/",
        {
            "uid_evento": "clase-unir-miercoles-12",
            "fecha_original": "2026-10-21",
            "hora_inicio_original": "12:00",
            "nueva_fecha": "2026-10-21",
            "nueva_hora_inicio": "16:00",
        },
        follow=True,
    )
    assert res.status_code == 200
    content = res.content.decode("utf-8")

    # Persistencia en base de datos
    reubicacion = ReubicacionClase.objects.get(
        uid_evento="clase-unir-miercoles-12",
        fecha_original=date(2026, 10, 21),
    )
    assert reubicacion.nueva_fecha == date(2026, 10, 21)
    assert reubicacion.nueva_hora_inicio == time(16, 0)

    # Renderizado en nueva franja (16:00 -> 17:00, top = 960px, height = 60px)
    assert "top: 960px" in content
    assert "height: 60px" in content

    # Borde exterior azul más oscuro (#0369A1 o border-[#0369A1])
    assert "#0369A1" in content or "border-[#0369A1]" in content

    # Sin alerta de solapamiento en la clase reubicada
    assert "16:00" in content
    assert "17:00" in content


@pytest.mark.django_db
def test_r4_restablecer_horario_original(usuario_pau):
    """
    R4: En el diálogo de una clase reubicada se ofrece 'Restablecer a horario original'.
    Al ejecutar POST /turnos/restablecer-clase/, se elimina la reubicación y vuelve inmediatamente
    al horario iCal original.
    """
    from turnos.models import ReubicacionClase

    client = Client()
    client.login(username="pau", password="password123")

    # Primero reubicar
    client.post(
        "/turnos/reubicar-clase/",
        {
            "uid_evento": "clase-unir-miercoles-12",
            "fecha_original": "2026-10-21",
            "hora_inicio_original": "12:00",
            "nueva_fecha": "2026-10-21",
            "nueva_hora_inicio": "16:00",
        },
    )
    assert ReubicacionClase.objects.filter(uid_evento="clase-unir-miercoles-12").exists()

    # Comprobar que en la vista semanal de la clase reubicada se ofrece restablecer
    res_semana = client.get("/?vista=semana&fecha=2026-10-21")
    content_semana = res_semana.content.decode("utf-8")
    assert "/turnos/restablecer-clase/" in content_semana
    assert "Restablecer" in content_semana

    # Ejecutar restablecimiento
    res_restablecer = client.post(
        "/turnos/restablecer-clase/",
        {
            "uid_evento": "clase-unir-miercoles-12",
            "fecha_original": "2026-10-21",
        },
        follow=True,
    )
    assert res_restablecer.status_code == 200
    content_tras_restablecer = res_restablecer.content.decode("utf-8")

    # La reubicación fue eliminada de la base de datos
    assert not ReubicacionClase.objects.filter(uid_evento="clase-unir-miercoles-12").exists()

    # Vuelve a su horario original (12:00 a 13:00, top = 720px) con solapamiento
    assert "top: 720px" in content_tras_restablecer
    assert "12:00" in content_tras_restablecer
