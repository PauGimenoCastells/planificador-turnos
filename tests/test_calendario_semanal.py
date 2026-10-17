from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import ConfiguracionTurno
from turnos.rotacion import obtener_eventos_semana


@pytest.fixture
def usuario_pau(db):
    user = User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(
        fecha_base=date(2026, 10, 12),
        turno_inicial="A",
    )
    return user


@pytest.fixture
def usuario_companero(db):
    return User.objects.create_user(username="companero1", password="password123")


@pytest.mark.django_db
def test_r1_portante_obtener_eventos_semana_estructura_y_bloques():
    """
    R1 (Portante): La función obtener_eventos_semana calcula 7 días (Lunes a Domingo)
    con bloques de fábrica y autobuses posicionados en sus franjas horarias exactas.
    """
    config = ConfiguracionTurno.obtener_activa()
    lunes = date(2026, 10, 12)  # Turno A

    semana = obtener_eventos_semana(fecha_lunes=lunes, config=config)

    assert len(semana) == 7
    dias_nombres = [d["nombre_dia"] for d in semana]
    assert dias_nombres == [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]

    # Lunes debe ser Turno A
    dia_lunes = semana[0]
    assert dia_lunes["fecha"] == lunes
    assert dia_lunes["codigo_turno"] == "A"
    assert dia_lunes["es_descanso"] is False

    bloques = dia_lunes["bloques"]
    tipos = [b["tipo"] for b in bloques]
    assert "bus_ida" in tipos
    assert "fabrica" in tipos
    assert "bus_vuelta" in tipos

    # Comprobación de franjas horarias exactas de Turno A
    bloque_fabrica = next(b for b in bloques if b["tipo"] == "fabrica")
    assert bloque_fabrica["hora_inicio_str"] == "05:45"
    assert bloque_fabrica["hora_fin_str"] == "13:45"
    assert bloque_fabrica["minuto_inicio"] == 5 * 60 + 45  # 345 min
    assert bloque_fabrica["minuto_fin"] == 13 * 60 + 45  # 825 min

    bloque_bus_ida = next(b for b in bloques if b["tipo"] == "bus_ida")
    assert bloque_bus_ida["hora_inicio_str"] == "05:00"
    assert bloque_bus_ida["hora_fin_str"] == "05:45"

    bloque_bus_vuelta = next(b for b in bloques if b["tipo"] == "bus_vuelta")
    assert bloque_bus_vuelta["hora_inicio_str"] == "14:00"
    assert bloque_bus_vuelta["hora_fin_str"] == "15:30"

    # Fin de semana (Sábado y Domingo): descanso, sin fábrica ni autobuses
    dia_sabado = semana[5]
    assert dia_sabado["es_descanso"] is True
    assert (
        len([b for b in dia_sabado["bloques"] if b["tipo"] in ("fabrica", "bus_ida", "bus_vuelta")])
        == 0
    )


@pytest.mark.django_db
def test_r1_vista_semanal_renderiza_eje_24_horas_y_navegacion(usuario_pau):
    """
    R1: GET /?vista=semana renderiza cuadrícula de 24 horas (00:00 a 24:00),
    columnas de Lunes a Domingo y enlaces de navegación entre semanas.
    """
    client = Client()
    client.login(username="pau", password="password123")

    response = client.get("/?vista=semana&fecha=2026-10-12")
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Debe contener eje de horas (00:00, 08:00, 12:00, 23:00 o similar)
    assert "00:00" in content
    assert "12:00" in content
    assert "23:00" in content or "24:00" in content

    # Columnas de Lunes a Domingo
    assert "Lunes" in content
    assert "Viernes" in content
    assert "Domingo" in content

    # Bloques de turno presentes
    assert "Turno A" in content or "05:45" in content

    # Botones o enlaces de navegación anterior / siguiente de semana
    assert "fecha=" in content or "semana=" in content or "offset=" in content


@pytest.mark.django_db
def test_r2_sidebar_mini_calendario_y_boton_hoy(usuario_pau):
    """
    R2: En vista semanal se muestra barra lateral izquierda con mini-calendario mensual navegable
    y botón 'Hoy' en la cabecera.
    """
    client = Client()
    client.login(username="pau", password="password123")

    response = client.get("/?vista=semana")
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Mini calendario en sidebar
    assert (
        "mini-calendario" in content
        or "sidebar" in content
        or "mes-mini" in content
        or "Calendario Uni" in content
    )
    # Botón Hoy
    assert "Hoy" in content


@pytest.mark.django_db
def test_r3_selector_vistas_mes_y_semana(usuario_pau):
    """
    R3: El selector de vistas permite alternar entre vista mensual y vista semanal horaria.
    """
    client = Client()
    client.login(username="pau", password="password123")

    # Vista mes
    res_mes = client.get("/?vista=mes")
    assert res_mes.status_code == 200
    content_mes = res_mes.content.decode("utf-8")
    assert "vista=semana" in content_mes
    assert "Mes" in content_mes

    # Vista semana
    res_semana = client.get("/?vista=semana")
    assert res_semana.status_code == 200
    content_semana = res_semana.content.decode("utf-8")
    assert "vista=mes" in content_semana
    assert "Semana" in content_semana


@pytest.mark.django_db
def test_permisos_solo_admin_y_pau_ven_rotar_y_ajustes(usuario_pau, usuario_companero):
    """
    Requisito web: Solo admin y pau pueden ver y realizar cambios en rotar turnos y ajustes.
    Compañeros no ven esas opciones ni pueden acceder a /turnos/configurar/.
    """
    client_pau = Client()
    client_pau.login(username="pau", password="password123")
    res_pau = client_pau.get("/")
    content_pau = res_pau.content.decode("utf-8")
    assert "/turnos/configurar/" in content_pau
    assert "Rotar" in content_pau or "rotar" in content_pau

    client_comp = Client()
    client_comp.login(username="companero1", password="password123")
    res_comp = client_comp.get("/")
    content_comp = res_comp.content.decode("utf-8")
    # No debe ver enlace a configurar turnos ni rotar
    assert "/turnos/configurar/" not in content_comp
    assert "+3 semanas (Rotar)" not in content_comp

    # Si intenta acceder directamente por URL a /turnos/configurar/, se le deniega (403 o redirect)
    res_post_comp = client_comp.get("/turnos/configurar/")
    assert res_post_comp.status_code in (403, 302)
