from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import (
    ConfiguracionTurno,
    ExcepcionTurnoSemana,
    FestivoParada,
    VigenciaRotacion,
)
from turnos.rotacion import ORDEN_ROTACION, obtener_turno_dia


@pytest.mark.django_db
def test_r1_navegacion_mensual_natural():
    """R1: Navegación mensual mes a mes natural con enlaces y título coherente."""
    pau = User.objects.create_user(username="pau", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 1, 1), turno_inicial="A")

    client = Client()
    client.force_login(pau)

    # 1. Petición a marzo 2026
    resp_marzo = client.get("/?vista=mes&fecha=2026-03-15")
    assert resp_marzo.status_code == 200
    assert resp_marzo.context["fecha_mes_anterior"] == "2026-02-01"
    assert resp_marzo.context["fecha_mes_siguiente"] == "2026-04-01"
    assert resp_marzo.context["titulo_mes_ano"] == "Marzo 2026"
    content_marzo = resp_marzo.content.decode("utf-8")
    assert "/?vista=mes&fecha=2026-02-01" in content_marzo
    assert "/?vista=mes&fecha=2026-04-01" in content_marzo
    assert "Marzo 2026" in content_marzo

    # 2. Petición a enero 2026 (límite de año anterior)
    resp_enero = client.get("/?vista=mes&fecha=2026-01-10")
    assert resp_enero.status_code == 200
    assert resp_enero.context["fecha_mes_anterior"] == "2025-12-01"
    assert resp_enero.context["fecha_mes_siguiente"] == "2026-02-01"
    assert resp_enero.context["titulo_mes_ano"] == "Enero 2026"

    # 3. Petición a diciembre 2026 (límite de año siguiente)
    resp_dic = client.get("/?vista=mes&fecha=2026-12-20")
    assert resp_dic.status_code == 200
    assert resp_dic.context["fecha_mes_anterior"] == "2026-11-01"
    assert resp_dic.context["fecha_mes_siguiente"] == "2027-01-01"
    assert resp_dic.context["titulo_mes_ano"] == "Diciembre 2026"


@pytest.mark.django_db
def test_r2_criterio_portante_resolucion_turno_por_vigencia_activa():
    """R2 (criterio portante): Resolución de turno histórico mediante VigenciaRotacion activa."""
    # Sin vigencias: fallback a ConfiguracionTurno
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 10, 12), turno_inicial="A")
    info_fallback = obtener_turno_dia(date(2026, 10, 14))  # Miércoles
    assert info_fallback["codigo"] == "A"

    # Se crean dos vigencias históricas
    v1 = VigenciaRotacion.objects.create(fecha_inicio=date(2026, 1, 1), turno_inicial="A")
    v2 = VigenciaRotacion.objects.create(fecha_inicio=date(2026, 7, 1), turno_inicial="C")

    assert str(v1) == "Vigencia desde 2026-01-01: Turno A"
    assert str(v2) == "Vigencia desde 2026-07-01: Turno C"

    # En mayo de 2026 (antes de la vigencia de julio): debe usar v1 (2026-01-01, Turno A)
    # Lunes 2025-12-29 es lunes_vigencia para 2026-01-01.
    fecha_mayo = date(2026, 5, 4)  # Lunes
    lunes_v1 = date(2026, 1, 1) - timedelta(days=date(2026, 1, 1).weekday())
    semanas_diff_mayo = (fecha_mayo - lunes_v1).days // 7
    bloques_diff_mayo = semanas_diff_mayo // 3
    esperado_mayo = ORDEN_ROTACION[bloques_diff_mayo % len(ORDEN_ROTACION)]
    info_mayo = obtener_turno_dia(fecha_mayo)
    assert info_mayo["codigo"] == esperado_mayo

    # En julio de 2026 (a partir del 1 de julio): debe usar v2 (2026-07-01, Turno C)
    # 2026-07-01 es miércoles -> lunes_vigencia es 2026-06-29.
    # El turno C debe mantenerse durante un bloque tri-semanal completo (3 semanas = 21 días)
    fecha_julio_sem1 = date(2026, 7, 1)  # Miércoles semana 1
    assert obtener_turno_dia(fecha_julio_sem1)["codigo"] == "C"

    # Semana 2 (lunes 2026-07-06): sigue en Turno C (semana 2 del bloque de 3 semanas)
    fecha_julio_sem2 = date(2026, 7, 6)
    assert obtener_turno_dia(fecha_julio_sem2)["codigo"] == "C"

    # Semana 3 (lunes 2026-07-13): sigue en Turno C (semana 3 del bloque de 3 semanas)
    fecha_julio_sem3 = date(2026, 7, 13)
    assert obtener_turno_dia(fecha_julio_sem3)["codigo"] == "C"

    # Semana 4 (lunes 2026-07-20, día 21 desde lunes_vigencia): pasa a Turno B (siguiente bloque de 3 semanas)
    fecha_julio_sem4 = date(2026, 7, 20)
    assert obtener_turno_dia(fecha_julio_sem4)["codigo"] == "B"


@pytest.mark.django_db
def test_r3_inalterabilidad_del_pasado_al_anadir_nueva_vigencia():
    """R3: Agregar una nueva vigencia a mitad de año reinicia el ciclo sin alterar los turnos pasados."""
    # Se establece vigencia de inicio de año
    VigenciaRotacion.objects.create(fecha_inicio=date(2026, 1, 1), turno_inicial="A")

    fecha_junio_1 = date(2026, 6, 8)  # Lunes
    fecha_junio_2 = date(2026, 6, 15)  # Lunes
    fecha_junio_3 = date(2026, 6, 22)  # Lunes

    turno_junio_1_antes = obtener_turno_dia(fecha_junio_1)["codigo"]
    turno_junio_2_antes = obtener_turno_dia(fecha_junio_2)["codigo"]
    turno_junio_3_antes = obtener_turno_dia(fecha_junio_3)["codigo"]

    # Pau crea a mitad de año una nueva vigencia para el 1 de julio de 2026 con Turno B
    VigenciaRotacion.objects.create(fecha_inicio=date(2026, 7, 1), turno_inicial="B")

    # Los turnos del pasado (junio) deben ser 100% IDÉNTICOS
    assert obtener_turno_dia(fecha_junio_1)["codigo"] == turno_junio_1_antes
    assert obtener_turno_dia(fecha_junio_2)["codigo"] == turno_junio_2_antes
    assert obtener_turno_dia(fecha_junio_3)["codigo"] == turno_junio_3_antes

    # El nuevo ciclo entra en vigor el 1 de julio con el turno nuevo B
    assert obtener_turno_dia(date(2026, 7, 1))["codigo"] == "B"


@pytest.mark.django_db
def test_r4_gestion_de_vigencias_permisos_y_creacion():
    """R4: Pau y admin pueden ver y crear vigencias; solicitantes reciben 403 Forbidden."""
    pau = User.objects.create_user(username="pau", password="password123")
    pol = User.objects.create_user(username="pol", password="password123")
    ConfiguracionTurno.objects.create(fecha_base=date(2026, 1, 1), turno_inicial="A")

    client_pol = Client()
    client_pol.force_login(pol)

    # 1. Solicitante pol intenta acceder a /configurar-turnos/ y /turnos/configurar/
    resp_pol_get1 = client_pol.get("/configurar-turnos/")
    assert resp_pol_get1.status_code == 403
    resp_pol_get2 = client_pol.get("/turnos/configurar/")
    assert resp_pol_get2.status_code == 403

    resp_pol_post = client_pol.post(
        "/configurar-turnos/",
        {"accion": "crear_vigencia", "fecha_inicio": "2026-07-01", "turno_inicial": "B"},
    )
    assert resp_pol_post.status_code == 403
    assert not VigenciaRotacion.objects.filter(fecha_inicio=date(2026, 7, 1)).exists()

    # 2. Pau accede y ve el panel y las vigencias
    client_pau = Client()
    client_pau.force_login(pau)

    resp_pau_get = client_pau.get("/configurar-turnos/")
    assert resp_pau_get.status_code == 200
    assert "Vigencias de Rotación de Turnos" in resp_pau_get.content.decode("utf-8")

    # 3. Pau crea vigencia por POST
    resp_pau_post = client_pau.post(
        "/configurar-turnos/",
        {"accion": "crear_vigencia", "fecha_inicio": "2026-07-01", "turno_inicial": "B"},
    )
    assert resp_pau_post.status_code in (200, 302)
    vigencia_creada = VigenciaRotacion.objects.filter(fecha_inicio=date(2026, 7, 1)).first()
    assert vigencia_creada is not None
    assert vigencia_creada.turno_inicial == "B"


@pytest.mark.django_db
def test_r5_prioridad_de_excepciones_semanales_y_festivos_sobre_vigencia():
    """R5: ExcepcionTurnoSemana y FestivoParada mantienen prioridad sobre la vigencia activa."""
    # Vigencia activa asigna Turno A a partir del lunes 5 de octubre
    lunes_semana = date(2026, 10, 5)
    VigenciaRotacion.objects.create(fecha_inicio=lunes_semana, turno_inicial="A")

    # Comprobación base de la vigencia
    assert obtener_turno_dia(lunes_semana)["codigo"] == "A"

    # Excepción semanal en ese lunes fuerza Turno C
    ExcepcionTurnoSemana.objects.create(lunes_semana=lunes_semana, turno="C")
    martes = date(2026, 10, 6)
    assert obtener_turno_dia(martes)["codigo"] == "C"

    # Festivo o parada en miércoles 7 de octubre
    miercoles = date(2026, 10, 7)
    FestivoParada.objects.create(fecha=miercoles, es_festivo=True, motivo="Parada técnica")
    info_miercoles = obtener_turno_dia(miercoles)
    assert info_miercoles["es_festivo"] is True
    assert info_miercoles["fabrica"] is None
    assert "Parada técnica" in info_miercoles["motivo"]
