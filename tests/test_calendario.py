from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import ConfiguracionTurno


@pytest.mark.django_db
def test_r4_cuadricula_calendario_en_home_para_usuario_autenticado():
    """R4: Usuario autenticado visualiza cuadricula de calendario en / con acento #00CCFF."""
    User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(
        fecha_base=date(2026, 10, 12),
        turno_inicial="A",
    )

    client = Client()
    client.login(username="pau", password="password123")

    response = client.get("/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Debe contener la cuadricula de calendario y etiquetas de turnos
    assert "Calendario de Turnos" in content or "Turno" in content
    assert "#00CCFF" in content or "00CCFF" in content
    assert "Descanso" in content


@pytest.mark.django_db
def test_r5_configuracion_de_turnos_actualiza_proyeccion():
    """R5: En /turnos/configurar/ se actualiza fecha base y turno, reflejandose inmediatamente."""
    User.objects.create_user(username="pau", password="password123")
    client = Client()
    client.login(username="pau", password="password123")

    # Acceso GET al formulario
    response_get = client.get("/turnos/configurar/")
    assert response_get.status_code == 200
    content_get = response_get.content.decode("utf-8")
    assert "Configurar Turnos" in content_get or "fecha_base" in content_get

    # Actualizar via POST
    response_post = client.post(
        "/turnos/configurar/",
        {
            "fecha_base": "2026-11-02",
            "turno_inicial": "C",
        },
        follow=True,
    )
    assert response_post.status_code == 200

    config = ConfiguracionTurno.obtener_activa()
    assert str(config.fecha_base) == "2026-11-02"
    assert config.turno_inicial == "C"
