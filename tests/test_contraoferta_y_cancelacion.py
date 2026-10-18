from datetime import date, time, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from turnos.models import Cita, ConfiguracionTurno
from turnos.rotacion import (
    COLORES_SOLICITANTES,
    obtener_eventos_semana,
    obtener_franjas_disponibles_semana,
)


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
# R1: Leyenda visual de usuarios
# ==============================================================================
@pytest.mark.django_db
def test_r1_leyenda_visual_usuarios_en_vista_semanal(datos_test):
    """
    R1: Renderizado en la vista semanal de la leyenda con los nombres de Pol, Manolo, Paco y Random
    y sus respectivos colores HEX (#10B981, #F59E0B, #8B5CF6, #EC4899), visible tanto para Pau
    como para los solicitantes.
    """
    # 1. Comprobación de diccionario de colores
    assert COLORES_SOLICITANTES["pol"].upper() == "#10B981"
    assert COLORES_SOLICITANTES["manolo"].upper() == "#F59E0B"
    assert COLORES_SOLICITANTES["paco"].upper() == "#8B5CF6"
    assert COLORES_SOLICITANTES["random"].upper() == "#EC4899"

    client = Client()
    # Ver como Pau
    client.force_login(datos_test["pau"])
    resp = client.get("/?vista=semana")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "Pol" in html
    assert "#10B981" in html or "#10b981" in html
    assert "Manolo" in html
    assert "#F59E0B" in html or "#f59e0b" in html
    assert "Paco" in html
    assert "#8B5CF6" in html or "#8b5cf6" in html
    assert "Random" in html
    assert "#EC4899" in html or "#ec4899" in html

    # Ver como solicitante Pol
    client.force_login(datos_test["pol"])
    resp_pol = client.get("/?vista=semana")
    assert resp_pol.status_code == 200
    html_pol = resp_pol.content.decode("utf-8")
    assert "Pol" in html_pol
    assert "Manolo" in html_pol
    assert "Paco" in html_pol
    assert "Random" in html_pol


# ==============================================================================
# R2: Cancelación de citas por el solicitante
# ==============================================================================
@pytest.mark.django_db
def test_r2_cancelacion_cita_por_solicitante_y_liberacion_de_franja(datos_test):
    """
    R2: Un solicitante puede cancelar en cualquier momento una cita propia en estado
    'solicitada', 'confirmada' o 'contraoferta'. Pasa a 'cancelada' y libera la franja.
    Un usuario distinto no puede cancelar citas ajenas (403 Forbidden).
    """
    fecha_futura = date(2026, 10, 15)  # Jueves de semana Turno A (franja 15:35-19:45)
    cita_pol = Cita.objects.create(
        solicitante=datos_test["pol"],
        fecha=fecha_futura,
        hora_inicio=time(16, 0),
        hora_fin=time(17, 0),
        motivo="Reunión de coordinación Pol",
        estado="confirmada",
    )

    client_manolo = Client()
    client_manolo.force_login(datos_test["manolo"])
    # Manolo intenta cancelar la cita de Pol -> Debe dar 403 Forbidden
    resp_ajeno = client_manolo.post("/turnos/cancelar-cita/", {"cita_id": cita_pol.id})
    assert resp_ajeno.status_code == 403
    cita_pol.refresh_from_db()
    assert cita_pol.estado == "confirmada"

    # Pol cancela su propia cita
    client_pol = Client()
    client_pol.force_login(datos_test["pol"])
    resp_propio = client_pol.post("/turnos/cancelar-cita/", {"cita_id": cita_pol.id})
    assert resp_propio.status_code in (200, 302)
    cita_pol.refresh_from_db()
    assert cita_pol.estado == "cancelada"

    # La franja ahora está libre: 16:00-17:00 no debe estar bloqueada por la cita cancelada
    franjas = obtener_franjas_disponibles_semana(fecha_futura, config=datos_test["config"])
    franjas_dia = franjas[fecha_futura]
    # En Turno A, toda la franja 15:35-19:45 debe estar libre
    assert any(
        f["hora_inicio_str"] == "15:35" and f["hora_fin_str"] == "19:45" for f in franjas_dia
    )


# ==============================================================================
# R3: Contraoferta de horario por Pau/Admin (Criterio portante)
# ==============================================================================
@pytest.mark.django_db
def test_r3_contraoferta_de_horario_por_pau_o_admin(datos_test):
    """
    R3 (Criterio portante): Pau o Admin pueden enviar una contraoferta a una cita solicitada
    con nueva fecha, hora inicio, hora fin y mensaje explicativo (hasta 250 car.),
    pasando la cita al estado 'contraoferta'.
    """
    fecha_cita = date(2026, 10, 16)  # Viernes
    cita = Cita.objects.create(
        solicitante=datos_test["manolo"],
        fecha=fecha_cita,
        hora_inicio=time(16, 0),
        hora_fin=time(17, 0),
        motivo="Dudas de proyecto",
        estado="solicitada",
    )

    nueva_fecha = date(2026, 10, 16)
    nueva_hora_ini = time(17, 30)
    nueva_hora_fin = time(18, 30)
    mensaje = "A las 16:00 no puedo, te propongo a las 17:30 que tengo hueco tranquilo."

    # Intentar contraofertar como usuario no autorizado (ej. Pol) -> 403
    client_pol = Client()
    client_pol.force_login(datos_test["pol"])
    resp_pol = client_pol.post(
        "/turnos/contraofertar-cita/",
        {
            "cita_id": cita.id,
            "nueva_fecha": nueva_fecha.isoformat(),
            "nueva_hora_inicio": nueva_hora_ini.strftime("%H:%M"),
            "nueva_hora_fin": nueva_hora_fin.strftime("%H:%M"),
            "mensaje_contraoferta": mensaje,
        },
    )
    assert resp_pol.status_code == 403

    # Pau realiza la contraoferta
    client_pau = Client()
    client_pau.force_login(datos_test["pau"])
    resp_pau = client_pau.post(
        "/turnos/contraofertar-cita/",
        {
            "cita_id": cita.id,
            "nueva_fecha": nueva_fecha.isoformat(),
            "nueva_hora_inicio": nueva_hora_ini.strftime("%H:%M"),
            "nueva_hora_fin": nueva_hora_fin.strftime("%H:%M"),
            "mensaje_contraoferta": mensaje,
        },
    )
    assert resp_pau.status_code in (200, 302)

    cita.refresh_from_db()
    assert cita.estado == "contraoferta"
    assert cita.fecha_propuesta == nueva_fecha
    assert cita.hora_inicio_propuesta == nueva_hora_ini
    assert cita.hora_fin_propuesta == nueva_hora_fin
    assert cita.mensaje_contraoferta == mensaje


# ==============================================================================
# R4: Aceptación o rechazo de contraoferta por el solicitante
# ==============================================================================
@pytest.mark.django_db
def test_r4_aceptacion_o_rechazo_de_contraoferta_por_solicitante(datos_test):
    """
    R4: El solicitante ve la propuesta; si acepta, la cita actualiza fecha y horas
    oficiales y pasa a 'confirmada'; si rechaza, pasa a 'rechazada'.
    """
    fecha_orig = date(2026, 10, 16)
    fecha_prop = date(2026, 10, 17)  # Sábado fin de semana
    cita = Cita.objects.create(
        solicitante=datos_test["manolo"],
        fecha=fecha_orig,
        hora_inicio=time(16, 0),
        hora_fin=time(17, 0),
        motivo="Revisión",
        estado="contraoferta",
        fecha_propuesta=fecha_prop,
        hora_inicio_propuesta=time(10, 0),
        hora_fin_propuesta=time(11, 0),
        mensaje_contraoferta="El sábado por la mañana me viene mejor",
    )

    client_manolo = Client()
    client_manolo.force_login(datos_test["manolo"])

    # 1. Manolo ve la contraoferta en la vista semanal
    resp_semana = client_manolo.get("/?vista=semana")
    assert resp_semana.status_code == 200
    html = resp_semana.content.decode("utf-8")
    assert "El sábado por la mañana me viene mejor" in html
    assert "contraoferta" in html.lower() or "propuesta" in html.lower()

    # 2. Otro solicitante no puede responder a la contraoferta de Manolo
    client_paco = Client()
    client_paco.force_login(datos_test["paco"])
    resp_paco = client_paco.post(
        "/turnos/responder-contraoferta/",
        {"cita_id": cita.id, "accion": "aceptar"},
    )
    assert resp_paco.status_code == 403

    # 3. Manolo acepta la contraoferta
    resp_aceptar = client_manolo.post(
        "/turnos/responder-contraoferta/",
        {"cita_id": cita.id, "accion": "aceptar"},
    )
    assert resp_aceptar.status_code in (200, 302)

    cita.refresh_from_db()
    assert cita.estado == "confirmada"
    assert cita.fecha == fecha_prop
    assert cita.hora_inicio == time(10, 0)
    assert cita.hora_fin == time(11, 0)

    # 4. Caso de rechazo con otra cita
    cita_rechazar = Cita.objects.create(
        solicitante=datos_test["paco"],
        fecha=fecha_orig,
        hora_inicio=time(17, 0),
        hora_fin=time(18, 0),
        motivo="Consulta",
        estado="contraoferta",
        fecha_propuesta=fecha_prop,
        hora_inicio_propuesta=time(11, 30),
        hora_fin_propuesta=time(12, 30),
        mensaje_contraoferta="Prefiero a las 11:30",
    )
    client_paco.force_login(datos_test["paco"])
    resp_rechazar = client_paco.post(
        "/turnos/responder-contraoferta/",
        {"cita_id": cita_rechazar.id, "accion": "rechazar"},
    )
    assert resp_rechazar.status_code in (200, 302)
    cita_rechazar.refresh_from_db()
    assert cita_rechazar.estado == "rechazada"


# ==============================================================================
# R5: Validación de contraoferta en franja hábil y antelación mínima
# ==============================================================================
@pytest.mark.django_db
def test_r5_validacion_contraoferta_franja_habil_y_antelacion(datos_test):
    """
    R5: La contraoferta propuesta por Pau debe caer dentro de una franja disponible
    válida y con al menos 12 horas de antelación. Si cae fuera o tiene <12h, se rechaza (400).
    """
    fecha_futura = date(2026, 10, 16)  # Viernes Turno A (disponible: 15:35-19:45)
    cita = Cita.objects.create(
        solicitante=datos_test["pol"],
        fecha=fecha_futura,
        hora_inicio=time(16, 0),
        hora_fin=time(17, 0),
        motivo="Revisión",
        estado="solicitada",
    )

    client_pau = Client()
    client_pau.force_login(datos_test["pau"])

    # Contraoferta fuera de franja (ej: 09:00 en Turno A, que es fábrica/mañana)
    resp_fuera = client_pau.post(
        "/turnos/contraofertar-cita/",
        {
            "cita_id": cita.id,
            "nueva_fecha": fecha_futura.isoformat(),
            "nueva_hora_inicio": "09:00",
            "nueva_hora_fin": "10:00",
            "mensaje_contraoferta": "Te propongo a las 9",
        },
    )
    assert resp_fuera.status_code == 400
    assert "franja disponible" in resp_fuera.content.decode("utf-8").lower()

    # Contraoferta con menos de 12h de antelación
    ahora = timezone.now()
    en_tres_horas = ahora + timedelta(hours=3)
    resp_antelacion = client_pau.post(
        "/turnos/contraofertar-cita/",
        {
            "cita_id": cita.id,
            "nueva_fecha": en_tres_horas.date().isoformat(),
            "nueva_hora_inicio": en_tres_horas.time().strftime("%H:%M"),
            "nueva_hora_fin": (en_tres_horas + timedelta(hours=1)).time().strftime("%H:%M"),
            "mensaje_contraoferta": "En 3 horas nos vemos",
        },
    )
    assert resp_antelacion.status_code == 400
    assert "12 horas" in resp_antelacion.content.decode("utf-8").lower()


# ==============================================================================
# R6: Clases universitarias fuera de disponibilidad tratadas como conflicto
# ==============================================================================
@pytest.mark.django_db
def test_r6_clases_universitarias_fuera_de_disponibilidad_conflicto(datos_test):
    """
    R6: Si una clase universitaria ocurre fuera de la franja disponible base del turno de Pau:
    - Turno A: 15:35-19:45 (ej: clase a las 20:30 o a las 14:00)
    - Turno B: 08:00-12:30 (ej: clase a las 07:00 o a las 12:45)
    - Turno C: 15:30-20:15 (ej: clase a las 10:00 durante descanso/sueño del turno de noche)
    - Fines de semana: 08:00-22:00
    Se marca con tiene_solapamiento = True y motivo_solapamiento indicando fuera de franja de disponibilidad.
    """
    config = datos_test["config"]
    # Turno C: lunes 2 de noviembre de 2026
    lunes_c = date(2026, 11, 2)
    # Clase universitaria a las 10:00-12:00 (en Turno C, fábrica es 21:45-05:45 y bus 06:00-07:30.
    # Las 10:00 es descanso/sueño de Pau, fuera de franja 15:30-20:15)
    eventos_ical = [
        {
            "uid_evento": "clase-uni-c-1",
            "titulo": "Sistemas Distribuidos",
            "fecha": lunes_c,
            "hora_inicio_str": "10:00",
            "hora_fin_str": "12:00",
            "minuto_inicio": 600,
            "minuto_fin": 720,
            "es_hito": False,
        }
    ]

    eventos = obtener_eventos_semana(
        fecha_lunes=lunes_c,
        config=config,
        eventos_ical=eventos_ical,
        usuario=datos_test["pau"],
    )

    dia_lunes = eventos[0]
    clase_bloque = next(b for b in dia_lunes["bloques"] if b.get("uid_evento") == "clase-uni-c-1")

    assert clase_bloque["tiene_solapamiento"] is True
    assert "fuera de franja de disponibilidad" in clase_bloque["motivo_solapamiento"].lower()


# ==============================================================================
# UNIDAD 010: Acciones de confirmar, rechazar y contraoferta en modal de cuadrícula
# ==============================================================================
@pytest.mark.django_db
def test_acciones_cita_modal_cuadricula_para_pau(datos_test):
    """
    R1-R3: En el modal de detalle de cita de la cuadrícula (#modal-detalle-cita),
    cuando Pau o el admin está conectado, para citas en estado 'solicitada'
    deben estar disponibles los botones y formularios de:
    - Confirmar (/turnos/confirmar-cita/)
    - Rechazar (/turnos/rechazar-cita/)
    - Contraoferta (botón con acción para abrir contraoferta)
    Mientras que para un solicitante normal (ej. Pol) no deben aparecer opciones de gestión de Pau.
    """
    lunes = date(2026, 10, 19)
    _cita = Cita.objects.create(
        solicitante=datos_test["pol"],
        fecha=lunes + timedelta(days=1),
        hora_inicio=time(16, 0),
        hora_fin=time(17, 0),
        motivo="Revisión de ejercicios",
        estado="solicitada",
    )

    client_pau = Client()
    client_pau.force_login(datos_test["pau"])
    resp_pau = client_pau.get(f"/?vista=semana&fecha={lunes.isoformat()}")
    assert resp_pau.status_code == 200
    html_pau = resp_pau.content.decode("utf-8")

    # En el modal de detalle de cita deben existir las opciones de gestión para Pau
    assert 'id="modal-detalle-acciones-gestor"' in html_pau
    assert 'action="/turnos/confirmar-cita/"' in html_pau
    assert 'action="/turnos/rechazar-cita/"' in html_pau
    assert 'id="modal-confirmar-cita-id"' in html_pau
    assert 'id="modal-rechazar-cita-id"' in html_pau
    assert 'id="btn-detalle-contraoferta"' in html_pau

    # Para el solicitante Pol no deben figurar los botones de gestión de gestor en su vista
    client_pol = Client()
    client_pol.force_login(datos_test["pol"])
    resp_pol = client_pol.get(f"/?vista=semana&fecha={lunes.isoformat()}")
    assert resp_pol.status_code == 200
    html_pol = resp_pol.content.decode("utf-8")
    assert 'id="modal-detalle-acciones-gestor"' not in html_pol
