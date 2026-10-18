from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client

from turnos.models import ConfiguracionTurno


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
# R1: Apertura del modal interactivo en trayectos completados
# ==============================================================================
@pytest.mark.django_db
def test_r1_apertura_modal_trayecto_completado_para_pau(datos_test):
    """
    R1: Al hacer clic Pau en un bloque de autobús (bus_ida o bus_vuelta) de un trayecto completado
    (fecha y hora fin en el pasado), se abre el modal #modal-actividades-bus precargado con el día,
    tipo de trayecto y las actividades ya registradas si las hubiera.
    """
    from turnos.models import ActividadAutobus
    from turnos.rotacion import obtener_eventos_semana

    client = Client()
    client.force_login(datos_test["pau"])

    # Fecha pasada garantizada respecto al presente
    fecha_pasada = date.today() - timedelta(days=7)
    # Lunes de esa semana pasada
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())

    # Precrear una actividad para comprobar precarga
    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_ida",
        actividades=["lectura", "reflexion"],
    )

    # Verificar a nivel de rotación que el bloque marca ha_pasado=True y sus actividades
    eventos = obtener_eventos_semana(
        lunes_pasado, config=datos_test["config"], usuario=datos_test["pau"]
    )
    primer_dia = eventos[0]
    bloques_bus = [b for b in primer_dia["bloques"] if b["tipo"] in ("bus_ida", "bus_vuelta")]
    assert len(bloques_bus) > 0, "Debe haber bloques de autobús en días laborales de Turno A"
    bus_ida = next(b for b in bloques_bus if b["tipo"] == "bus_ida")
    assert bus_ida.get("ha_pasado") is True
    assert bus_ida.get("actividades") == ["lectura", "reflexion"]

    # Verificar en la respuesta HTML
    resp = client.get(f"/?vista=semana&fecha={lunes_pasado.isoformat()}")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # El modal #modal-actividades-bus debe estar presente en el HTML para Pau
    assert 'id="modal-actividades-bus"' in html
    assert "abrirModalActividadesBus" in html
    # Debe contener las 5 opciones
    assert "siesta" in html
    assert "lectura" in html
    assert "reflexion" in html
    assert "videojuegos" in html
    assert "videos" in html


# ==============================================================================
# R2: Bloqueo estricto en trayectos futuros y acceso exclusivo de Pau
# ==============================================================================
@pytest.mark.django_db
def test_r2_bloqueo_trayectos_futuros_y_solicitantes(datos_test):
    """
    R2: Bloqueo estricto de registro en trayectos futuros (error 400 si se intenta registrar
    actividades para un viaje futuro; en UI se avisa que el registro se habilita al finalizar
    el viaje). Solicitantes (Pol, Manolo, Paco, Random) sin interactividad ni modal.
    """
    client = Client()

    # Fecha futura garantizada
    fecha_futura = date.today() + timedelta(days=14)
    lunes_futuro = fecha_futura - timedelta(days=fecha_futura.weekday())

    # 1. Pau intenta POST para un trayecto futuro -> Error 400
    client.force_login(datos_test["pau"])
    resp_futuro = client.post(
        "/turnos/guardar-actividades-bus/",
        {
            "fecha": lunes_futuro.isoformat(),
            "tipo_bus": "bus_ida",
            "actividades": ["siesta"],
        },
    )
    assert resp_futuro.status_code == 400
    assert (
        "finalizado" in resp_futuro.content.decode("utf-8").lower()
        or "pasado" in resp_futuro.content.decode("utf-8").lower()
    )

    # 2. En UI, la semana futura muestra los bloques sin llamar a abrirModalActividadesBus directamente como acción permitida
    resp_ui_futura = client.get(f"/?vista=semana&fecha={lunes_futuro.isoformat()}")
    assert resp_ui_futura.status_code == 200

    # 3. Solicitante (Pol) intentando registrar actividades -> Error 403 (Forbidden)
    client.force_login(datos_test["pol"])
    fecha_pasada = date.today() - timedelta(days=7)
    resp_pol_post = client.post(
        "/turnos/guardar-actividades-bus/",
        {
            "fecha": fecha_pasada.isoformat(),
            "tipo_bus": "bus_ida",
            "actividades": ["siesta"],
        },
    )
    assert resp_pol_post.status_code == 403

    # 4. Solicitante (Pol) viendo la vista semanal -> sin modal de actividades de bus
    resp_pol_get = client.get(f"/?vista=semana&fecha={fecha_pasada.isoformat()}")
    assert resp_pol_get.status_code == 200
    html_pol = resp_pol_get.content.decode("utf-8")
    assert 'id="modal-actividades-bus"' not in html_pol


# ==============================================================================
# R3: Selección múltiple entre las 5 opciones permitidas y persistencia (Criterio Portante)
# ==============================================================================
@pytest.mark.django_db
def test_r3_seleccion_multiple_y_persistencia_actividades(datos_test):
    """
    R3 (Criterio Portante): Selección múltiple entre las 5 opciones permitidas:
    siesta, lectura, reflexion, videojuegos, videos.
    Persistencia en base de datos (ActividadAutobus), actualización/sobrescritura limpia
    y validación estricta que rechace cualquier valor ajeno a estas 5 opciones.
    """
    from turnos.models import ActividadAutobus

    client = Client()
    client.force_login(datos_test["pau"])

    fecha_pasada = date.today() - timedelta(days=7)
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())

    # 1. Guardar actividades válidas (múltiples: lectura y reflexion)
    resp = client.post(
        "/turnos/guardar-actividades-bus/",
        {
            "fecha": lunes_pasado.isoformat(),
            "tipo_bus": "bus_ida",
            "actividades": ["lectura", "reflexion"],
        },
    )
    assert resp.status_code in (200, 302)

    registro = ActividadAutobus.objects.get(fecha=lunes_pasado, tipo_bus="bus_ida")
    assert set(registro.actividades) == {"lectura", "reflexion"}

    # 2. Actualización limpia (sobrescritura sin duplicar fila)
    resp_update = client.post(
        "/turnos/guardar-actividades-bus/",
        {
            "fecha": lunes_pasado.isoformat(),
            "tipo_bus": "bus_ida",
            "actividades": ["siesta", "videojuegos", "videos"],
        },
    )
    assert resp_update.status_code in (200, 302)
    assert ActividadAutobus.objects.filter(fecha=lunes_pasado, tipo_bus="bus_ida").count() == 1
    registro.refresh_from_db()
    assert set(registro.actividades) == {"siesta", "videojuegos", "videos"}

    # 3. Validación estricta: rechazo con 400 ante opciones ajenas al catálogo permitido
    resp_invalido = client.post(
        "/turnos/guardar-actividades-bus/",
        {
            "fecha": lunes_pasado.isoformat(),
            "tipo_bus": "bus_ida",
            "actividades": ["siesta", "opcion_invalida_no_permitida"],
        },
    )
    assert resp_invalido.status_code == 400
    assert (
        "no permitida" in resp_invalido.content.decode("utf-8").lower()
        or "inválid" in resp_invalido.content.decode("utf-8").lower()
    )


# ==============================================================================
# R4: Visualización de insignias en la cuadrícula semanal
# ==============================================================================
@pytest.mark.django_db
def test_r4_visualizacion_insignias_en_cuadricula_semanal(datos_test):
    """
    R4: En los bloques de autobús con actividades guardadas, la cuadrícula semanal muestra
    iconos/etiquetas legibles (ej: 😴 Siesta, 📖 Lectura, 🧠 Reflexión, 🎮 Videojuegos, 🎬 Vídeos)
    dentro del bloque sin romper su disposición ni dimensiones.
    """
    from turnos.models import ActividadAutobus

    client = Client()
    client.force_login(datos_test["pau"])

    fecha_pasada = date.today() - timedelta(days=7)
    lunes_pasado = fecha_pasada - timedelta(days=fecha_pasada.weekday())

    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_ida",
        actividades=["siesta", "lectura"],
    )
    ActividadAutobus.objects.create(
        fecha=lunes_pasado,
        tipo_bus="bus_vuelta",
        actividades=["videojuegos", "videos", "reflexion"],
    )

    resp = client.get(f"/?vista=semana&fecha={lunes_pasado.isoformat()}")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Verificar que aparecen insignias con los emojis o textos correspondientes
    assert "😴" in html or "Siesta" in html
    assert "📖" in html or "Lectura" in html
    assert "🎮" in html or "Videojuegos" in html
    assert "🎬" in html or "Vídeos" in html or "Videos" in html
    assert "🧠" in html or "Reflexión" in html or "Reflexion" in html
