from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.ical import parsear_feed_ical
from turnos.models import ConfiguracionTurno
from turnos.rotacion import obtener_eventos_semana

EJEMPLO_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Universidad de Prueba//Horarios//ES
CALSCALE:GREGORIAN
BEGIN:VTIMEZONE
TZID:Europe/Madrid
BEGIN:STANDARD
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
TZNAME:CET
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
TZNAME:CEST
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
SUMMARY:Sistemas Distribuidos
DESCRIPTION:Aula 2.1 - Teoría
DTSTART;TZID=Europe/Madrid:20261012T160000
DTEND;TZID=Europe/Madrid:20261012T180000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20261220T235959
END:VEVENT
BEGIN:VEVENT
SUMMARY:Práctica Robótica (Solape Turno A)
DESCRIPTION:Laboratorio L3
DTSTART;TZID=Europe/Madrid:20261013T100000
DTEND;TZID=Europe/Madrid:20261013T120000
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def usuario_pau(db):
    user = User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(
        fecha_base=date(2026, 10, 12),
        turno_inicial="A",
    )
    return user


@pytest.mark.django_db
def test_r4_formulario_configurar_ical_get_y_post(usuario_pau):
    """
    R4: En /turnos/calendario-uni/ se puede visualizar el formulario para introducir
    la URL iCal universitaria y guardarla vía POST.
    """
    client = Client()
    client.login(username="pau", password="password123")

    # GET formulario
    response_get = client.get("/turnos/calendario-uni/")
    assert response_get.status_code == 200
    content_get = response_get.content.decode("utf-8")
    assert "url_ical_uni" in content_get or "url_ical" in content_get
    assert "Calendario Universitario" in content_get or "iCal" in content_get

    # POST guardar URL
    url_prueba = "https://universidad.example.edu/horarios/pau.ics"
    response_post = client.post(
        "/turnos/calendario-uni/",
        {"url_ical_uni": url_prueba},
        follow=True,
    )
    assert response_post.status_code == 200

    config = ConfiguracionTurno.obtener_activa()
    assert config.url_ical_uni == url_prueba


def test_r5_parser_ical_extrae_eventos_y_recurrencias():
    """
    R5: El parser de iCal extrae eventos VEVENT recurrentes y no recurrentes
    dentro del rango de fechas dado en Europe/Madrid.
    """
    fecha_inicio = date(2026, 10, 12)
    fecha_fin = date(2026, 10, 18)

    eventos = parsear_feed_ical(EJEMPLO_ICS, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)

    assert (
        len(eventos) >= 3
    )  # Lunes 12 (Sist. Dist.), Martes 13 (Robótica), Miércoles 14 (Sist. Dist.)

    titulos = [e["titulo"] for e in eventos]
    assert "Sistemas Distribuidos" in titulos
    assert "Práctica Robótica (Solape Turno A)" in titulos

    evento_lunes = next(
        e
        for e in eventos
        if e["titulo"] == "Sistemas Distribuidos" and e["fecha"] == date(2026, 10, 12)
    )
    assert evento_lunes["hora_inicio_str"] == "16:00"
    assert evento_lunes["hora_fin_str"] == "18:00"
    assert evento_lunes["minuto_inicio"] == 16 * 60
    assert evento_lunes["minuto_fin"] == 18 * 60


@pytest.mark.django_db
def test_r5_deteccion_de_solapamiento_entre_clase_y_turno():
    """
    R5: Si una clase universitaria coincide temporalmente con un turno de fábrica
    o trayecto de autobús, se marca la alerta de solapamiento.
    """
    config = ConfiguracionTurno.obtener_activa()
    lunes = date(2026, 10, 12)  # Turno A: fábrica 05:45-13:45, bus 05:00-05:45 y 14:00-15:30

    eventos_prueba = [
        {
            "titulo": "Clase Libre Tarde",
            "fecha": date(2026, 10, 12),
            "hora_inicio_str": "16:00",
            "hora_fin_str": "18:00",
            "minuto_inicio": 16 * 60,
            "minuto_fin": 18 * 60,
        },
        {
            "titulo": "Clase en Conflicto Fabrica",
            "fecha": date(2026, 10, 13),  # Martes Turno A
            "hora_inicio_str": "10:00",
            "hora_fin_str": "12:00",
            "minuto_inicio": 10 * 60,
            "minuto_fin": 12 * 60,
        },
    ]

    semana = obtener_eventos_semana(fecha_lunes=lunes, config=config, eventos_ical=eventos_prueba)

    # Lunes: clase a las 16:00 (en franja libre 15:35-19:45) -> Sin solapamiento
    dia_lunes = semana[0]
    clase_lunes = next(b for b in dia_lunes["bloques"] if b["tipo"] == "clase")
    assert clase_lunes["tiene_solapamiento"] is False

    # Martes: clase a las 10:00 (dentro de fábrica 05:45-13:45) -> Con solapamiento
    dia_martes = semana[1]
    clase_martes = next(b for b in dia_martes["bloques"] if b["tipo"] == "clase")
    assert clase_martes["tiene_solapamiento"] is True
    assert (
        "Turno A" in clase_martes["motivo_solapamiento"]
        or "fábrica" in clase_martes["motivo_solapamiento"].lower()
    )


@pytest.mark.django_db
def test_r5_vista_semanal_renderiza_clases_y_alerta_solapamiento(usuario_pau):
    """
    R5: En la vista semanal, los bloques de clase aparecen con el color de acento #00CCFF
    y los bloques en conflicto muestran indicador visual de alerta.
    """
    config = ConfiguracionTurno.obtener_activa()
    config.contenido_ical_cache = EJEMPLO_ICS
    config.save()

    client = Client()
    client.login(username="pau", password="password123")

    response = client.get("/?vista=semana&fecha=2026-10-12")
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    assert "Sistemas Distribuidos" in content
    assert "Práctica Robótica" in content
    # Indicador de alerta o conflicto presente
    assert (
        "conflicto" in content.lower()
        or "solapamiento" in content.lower()
        or "alerta" in content.lower()
    )
