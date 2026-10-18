from datetime import date, time, timedelta
from typing import Any

COLORES_SOLICITANTES = {
    "pol": "#10B981",
    "manolo": "#F59E0B",
    "paco": "#8B5CF6",
    "random": "#EC4899",
}


def obtener_color_solicitante(username: str) -> str:
    """Retorna el color hexadecimal asignado a un solicitante."""
    return COLORES_SOLICITANTES.get(username.lower(), "#10B981")


ORDEN_ROTACION = ["A", "C", "B"]

HORARIOS_TURNOS = {
    "A": {
        "nombre": "Turno A · Mañana",
        "color": "#00CCFF",
        "fabrica": "05:45–13:45",
        "bus_ida": "05:00–05:45",
        "bus_vuelta": "14:00–15:30",
        "franja_libre": "15:35–19:45",
    },
    "B": {
        "nombre": "Turno B · Tarde",
        "color": "#F59E0B",
        "fabrica": "13:45–21:45",
        "bus_ida": "13:00–13:45",
        "bus_vuelta": "22:00–23:30",
        "franja_libre": "08:00–12:30",
    },
    "C": {
        "nombre": "Turno C · Noche",
        "color": "#8B5CF6",
        "fabrica": "21:45–05:45",
        "bus_ida": "21:00–21:45",
        "bus_vuelta": "06:00–07:30",
        "franja_libre": "15:30–20:15",
    },
}


def obtener_turno_dia(
    fecha: date,
    fecha_base: date | None = None,
    turno_inicial: str = "A",
    config: Any | None = None,
) -> dict[str, Any]:
    """Calcula el turno correspondiente a una fecha segun el ciclo determinista de 21 dias."""
    if config is not None:
        fecha_base = config.fecha_base
        turno_inicial = config.turno_inicial
    elif fecha_base is None:
        from turnos.models import ConfiguracionTurno

        cfg = ConfiguracionTurno.obtener_activa()
        fecha_base = cfg.fecha_base
        turno_inicial = cfg.turno_inicial

    # Sabados (5) y Domingos (6) son descanso semanal (R3)
    if fecha.weekday() in (5, 6):
        return {
            "fecha": fecha,
            "es_descanso": True,
            "codigo": None,
            "nombre": "Descanso",
            "color": "#94A3B8",
            "fabrica": None,
            "bus_ida": None,
            "bus_vuelta": None,
            "franja_libre": "Día completo",
        }

    # Calculo determinista del bloque de 21 dias (R1)
    dias_diferencia = (fecha - fecha_base).days
    bloques_21 = dias_diferencia // 21
    idx_inicio = ORDEN_ROTACION.index(turno_inicial)
    idx_actual = (idx_inicio + bloques_21) % len(ORDEN_ROTACION)
    codigo = ORDEN_ROTACION[idx_actual]
    horario = HORARIOS_TURNOS[codigo]

    return {
        "fecha": fecha,
        "es_descanso": False,
        "codigo": codigo,
        "nombre": horario["nombre"],
        "color": horario["color"],
        "fabrica": horario["fabrica"],
        "bus_ida": horario["bus_ida"],
        "bus_vuelta": horario["bus_vuelta"],
        "franja_libre": horario["franja_libre"],
    }


def generar_bloques_dia_turno(codigo_turno: str, fecha: date) -> list[dict[str, Any]]:
    """Genera los bloques horarios de fábrica y autobuses para un día según el turno."""
    if codigo_turno == "A":
        return [
            {
                "tipo": "bus_ida",
                "titulo": "Bus Ida · Fábrica",
                "hora_inicio_str": "05:00",
                "hora_fin_str": "05:45",
                "minuto_inicio": 300,
                "minuto_fin": 345,
                "color_bg": "#E0F7FA",
                "color_borde": "#00CCFF",
                "color_texto": "#0E7490",
                "tiene_solapamiento": False,
                "motivo_solapamiento": "",
            },
            {
                "tipo": "fabrica",
                "titulo": "Turno A · Mañana",
                "hora_inicio_str": "05:45",
                "hora_fin_str": "13:45",
                "minuto_inicio": 345,
                "minuto_fin": 825,
                "color_bg": "#CFFAFE",
                "color_borde": "#00CCFF",
                "color_texto": "#164E63",
                "tiene_solapamiento": False,
                "motivo_solapamiento": "",
            },
            {
                "tipo": "bus_vuelta",
                "titulo": "Bus Vuelta · Fábrica",
                "hora_inicio_str": "14:00",
                "hora_fin_str": "15:30",
                "minuto_inicio": 840,
                "minuto_fin": 930,
                "color_bg": "#E0F7FA",
                "color_borde": "#00CCFF",
                "color_texto": "#0E7490",
                "tiene_solapamiento": False,
                "motivo_solapamiento": "",
            },
        ]
    elif codigo_turno == "B":
        return [
            {
                "tipo": "bus_ida",
                "titulo": "Bus Ida · Fábrica",
                "hora_inicio_str": "13:00",
                "hora_fin_str": "13:45",
                "minuto_inicio": 780,
                "minuto_fin": 825,
                "color_bg": "#FEF3C7",
                "color_borde": "#F59E0B",
                "color_texto": "#92400E",
                "tiene_solapamiento": False,
                "motivo_solapamiento": "",
            },
            {
                "tipo": "fabrica",
                "titulo": "Turno B · Tarde",
                "hora_inicio_str": "13:45",
                "hora_fin_str": "21:45",
                "minuto_inicio": 825,
                "minuto_fin": 1305,
                "color_bg": "#FDE68A",
                "color_borde": "#F59E0B",
                "color_texto": "#78350F",
                "tiene_solapamiento": False,
                "motivo_solapamiento": "",
            },
            {
                "tipo": "bus_vuelta",
                "titulo": "Bus Vuelta · Fábrica",
                "hora_inicio_str": "22:00",
                "hora_fin_str": "23:30",
                "minuto_inicio": 1320,
                "minuto_fin": 1410,
                "color_bg": "#FEF3C7",
                "color_borde": "#F59E0B",
                "color_texto": "#92400E",
                "tiene_solapamiento": False,
                "motivo_solapamiento": "",
            },
        ]
    elif codigo_turno == "C":
        bloques: list[dict[str, Any]] = []
        if fecha.weekday() > 0:
            bloques.extend(
                [
                    {
                        "tipo": "fabrica",
                        "titulo": "Turno C · Fin Noche",
                        "hora_inicio_str": "00:00",
                        "hora_fin_str": "05:45",
                        "minuto_inicio": 0,
                        "minuto_fin": 345,
                        "color_bg": "#EDE9FE",
                        "color_borde": "#8B5CF6",
                        "color_texto": "#5B21B6",
                        "tiene_solapamiento": False,
                        "motivo_solapamiento": "",
                    },
                    {
                        "tipo": "bus_vuelta",
                        "titulo": "Bus Vuelta · Fábrica",
                        "hora_inicio_str": "06:00",
                        "hora_fin_str": "07:30",
                        "minuto_inicio": 360,
                        "minuto_fin": 450,
                        "color_bg": "#F5F3FF",
                        "color_borde": "#8B5CF6",
                        "color_texto": "#6D28D9",
                        "tiene_solapamiento": False,
                        "motivo_solapamiento": "",
                    },
                ]
            )
        if fecha.weekday() < 5:
            bloques.extend(
                [
                    {
                        "tipo": "bus_ida",
                        "titulo": "Bus Ida · Fábrica",
                        "hora_inicio_str": "21:00",
                        "hora_fin_str": "21:45",
                        "minuto_inicio": 1260,
                        "minuto_fin": 1305,
                        "color_bg": "#F5F3FF",
                        "color_borde": "#8B5CF6",
                        "color_texto": "#6D28D9",
                        "tiene_solapamiento": False,
                        "motivo_solapamiento": "",
                    },
                    {
                        "tipo": "fabrica",
                        "titulo": "Turno C · Noche",
                        "hora_inicio_str": "21:45",
                        "hora_fin_str": "24:00",
                        "minuto_inicio": 1305,
                        "minuto_fin": 1440,
                        "color_bg": "#EDE9FE",
                        "color_borde": "#8B5CF6",
                        "color_texto": "#5B21B6",
                        "tiene_solapamiento": False,
                        "motivo_solapamiento": "",
                    },
                ]
            )
        return bloques
    return []


def restar_intervalo(
    intervalos: list[tuple[int, int]], ocupado: tuple[int, int]
) -> list[tuple[int, int]]:
    """Resta un intervalo ocupado [b_ini, b_fin] de una lista de intervalos libres."""
    b_ini, b_fin = ocupado
    if b_fin <= b_ini:
        return intervalos

    nuevos = []
    for s, e in intervalos:
        if b_fin <= s or b_ini >= e:
            nuevos.append((s, e))
        else:
            if s < b_ini:
                nuevos.append((s, b_ini))
            if b_fin < e:
                nuevos.append((b_fin, e))
    return nuevos


class FranjasSemana(dict):
    """Estructura de franjas disponibles que permite acceso por fecha, string ISO o índice numérico."""

    def __init__(self, dias_list: list[dict[str, Any]]) -> None:
        self._dias_list = dias_list
        super().__init__({item["fecha"]: item["franjas"] for item in dias_list})
        for item in dias_list:
            self[item["fecha"].isoformat()] = item["franjas"]

    def __getitem__(self, key: Any) -> list[dict[str, Any]]:
        if isinstance(key, int):
            return self._dias_list[key]["franjas"]
        return super().__getitem__(key)


def obtener_franjas_disponibles_semana(
    fecha_lunes: date,
    config: Any | None = None,
    eventos_ical: list[dict[str, Any]] | None = None,
) -> FranjasSemana:
    """Calcula las franjas de disponibilidad de Pau para cada día de la semana.

    Horarios base:
    - Turno A: 15:35 a 19:45 (minutos 935 a 1185)
    - Turno B: 08:00 a 12:30 (minutos 480 a 750)
    - Turno C: 15:30 a 20:15 (minutos 930 a 1215)
    - Fines de semana: 08:00 a 22:00 (minutos 480 a 1320)

    Descontando fábrica, buses, clases universitarias (incluidas reubicadas) y citas confirmadas.
    """
    lunes = fecha_lunes - timedelta(days=fecha_lunes.weekday())
    domingo = lunes + timedelta(days=6)

    if config is None:
        try:
            from turnos.models import ConfiguracionTurno

            config = ConfiguracionTurno.obtener_activa()
        except Exception:  # noqa: BLE001
            config = None

    if eventos_ical is None and config is not None and getattr(config, "contenido_ical_cache", ""):
        from turnos.ical import parsear_feed_ical

        eventos_ical = parsear_feed_ical(
            config.contenido_ical_cache,
            fecha_inicio=lunes,
            fecha_fin=domingo,
        )
    elif eventos_ical is None:
        eventos_ical = []

    # Cargar reubicaciones registradas para la configuración
    reubicaciones_map = {}
    if config is not None:
        try:
            from turnos.models import ReubicacionClase

            for r in ReubicacionClase.objects.filter(configuracion=config):
                reubicaciones_map[(r.uid_evento, r.fecha_original)] = r
        except Exception:  # noqa: BLE001, S110
            pass

    # Aplicar reubicaciones sobre los eventos iCal antes de distribuirlos por día
    clases_procesadas = []
    for ev in eventos_ical:
        ev_copy = dict(ev)
        if not ev_copy.get("es_hito"):
            uid = str(ev_copy.get("uid_evento") or ev_copy.get("id", ""))
            fecha_orig = ev_copy.get("fecha_original", ev_copy.get("fecha"))
            clave = (uid, fecha_orig)
            if clave in reubicaciones_map:
                r = reubicaciones_map[clave]
                duracion = max(ev_copy.get("minuto_fin", 0) - ev_copy.get("minuto_inicio", 0), 25)
                ev_copy["fecha"] = r.nueva_fecha
                nuevo_min_ini = r.nueva_hora_inicio.hour * 60 + r.nueva_hora_inicio.minute
                ev_copy["minuto_inicio"] = nuevo_min_ini
                ev_copy["minuto_fin"] = nuevo_min_ini + duracion
            clases_procesadas.append(ev_copy)

    dias_list = []
    for i in range(7):
        dia_fecha = lunes + timedelta(days=i)
        info_turno = obtener_turno_dia(dia_fecha, config=config)

        if dia_fecha.weekday() in (5, 6):
            intervalos_libres = [(480, 1320)]  # 08:00 - 22:00
        elif info_turno["codigo"] == "A":
            intervalos_libres = [(935, 1185)]  # 15:35 - 19:45
        elif info_turno["codigo"] == "B":
            intervalos_libres = [(480, 750)]  # 08:00 - 12:30
        elif info_turno["codigo"] == "C":
            intervalos_libres = [(930, 1215)]  # 15:30 - 20:15
        else:
            intervalos_libres = []

        # Descontar clases universitarias del día
        for c in clases_procesadas:
            if c.get("fecha") == dia_fecha:
                c_ini = c.get("minuto_inicio", 0)
                c_fin = c.get("minuto_fin", 0)
                intervalos_libres = restar_intervalo(intervalos_libres, (c_ini, c_fin))

        # Descontar citas confirmadas del día
        try:
            from turnos.models import Cita

            for cita in Cita.objects.filter(fecha=dia_fecha, estado="confirmada"):
                c_ini = cita.hora_inicio.hour * 60 + cita.hora_inicio.minute
                c_fin = cita.hora_fin.hour * 60 + cita.hora_fin.minute
                intervalos_libres = restar_intervalo(intervalos_libres, (c_ini, c_fin))
        except Exception:  # noqa: BLE001, S110
            pass

        franjas_dia = []
        for s, e in intervalos_libres:
            duracion = e - s
            if duracion > 0:
                h_ini, m_ini = s // 60, s % 60
                h_fin, m_fin = e // 60, e % 60
                franjas_dia.append(
                    {
                        "hora_inicio_str": f"{h_ini:02d}:{m_ini:02d}",
                        "hora_fin_str": f"{h_fin:02d}:{m_fin:02d}",
                        "hora_inicio": time(h_ini, m_ini),
                        "hora_fin": time(h_fin, m_fin) if e < 1440 else time(23, 59),
                        "minuto_inicio": s,
                        "minuto_fin": e,
                        "duracion_minutos": duracion,
                        "top_px": s,
                        "height_px": duracion,
                        "top_percent": round((s / 1440.0) * 100, 2),
                        "height_percent": round((duracion / 1440.0) * 100, 2),
                        "top_css": f"{(s / 1440.0) * 100:.2f}%",
                        "height_css": f"{(duracion / 1440.0) * 100:.2f}%",
                    }
                )

        dias_list.append({"fecha": dia_fecha, "franjas": franjas_dia})

    return FranjasSemana(dias_list)


def obtener_eventos_semana(
    fecha_lunes: date,
    config: Any | None = None,
    eventos_ical: list[dict[str, Any]] | None = None,
    usuario: Any | None = None,
) -> list[dict[str, Any]]:
    """Calcula para los 7 días de la semana (Lunes a Domingo) sus bloques horarios y solapamientos."""
    lunes = fecha_lunes - timedelta(days=fecha_lunes.weekday())
    domingo = lunes + timedelta(days=6)
    hoy = date.today()

    if config is None:
        try:
            from turnos.models import ConfiguracionTurno

            config = ConfiguracionTurno.obtener_activa()
        except Exception:  # noqa: BLE001
            config = None

    if eventos_ical is None and config is not None and getattr(config, "contenido_ical_cache", ""):
        from turnos.ical import parsear_feed_ical

        eventos_ical = parsear_feed_ical(
            config.contenido_ical_cache,
            fecha_inicio=lunes,
            fecha_fin=domingo,
        )
    elif eventos_ical is None:
        eventos_ical = []

    # Cargar franjas disponibles para toda la semana
    franjas_semana = obtener_franjas_disponibles_semana(
        fecha_lunes=lunes, config=config, eventos_ical=eventos_ical
    )

    # Determinar si el usuario es gestor para privacidad (R5)
    es_gestor = True
    if usuario is not None and getattr(usuario, "is_authenticated", False):
        es_gestor = bool(
            getattr(usuario, "username", "") in ("pau", "admin")
            or getattr(usuario, "is_superuser", False)
        )

    # Cargar reubicaciones registradas para la configuración
    reubicaciones_map = {}
    if config is not None:
        try:
            from turnos.models import ReubicacionClase

            for r in ReubicacionClase.objects.filter(configuracion=config):
                reubicaciones_map[(r.uid_evento, r.fecha_original)] = r
        except Exception:  # noqa: BLE001, S110
            pass

    # Aplicar reubicaciones sobre los eventos iCal antes de distribuirlos por día
    eventos_procesados = []
    for ev in eventos_ical:
        ev_copy = dict(ev)
        if not ev_copy.get("es_hito"):
            uid = str(ev_copy.get("uid_evento") or ev_copy.get("id", ""))
            fecha_orig = ev_copy.get("fecha_original", ev_copy.get("fecha"))
            hora_orig_str = ev_copy.get(
                "hora_inicio_original_str", ev_copy.get("hora_inicio_str", "")
            )
            ev_copy["uid_evento"] = uid
            ev_copy["fecha_original"] = fecha_orig
            ev_copy["hora_inicio_original_str"] = hora_orig_str

            clave = (uid, fecha_orig)
            if clave in reubicaciones_map:
                r = reubicaciones_map[clave]
                duracion = max(ev_copy.get("minuto_fin", 0) - ev_copy.get("minuto_inicio", 0), 25)
                ev_copy["fecha"] = r.nueva_fecha
                nuevo_min_ini = r.nueva_hora_inicio.hour * 60 + r.nueva_hora_inicio.minute
                nuevo_min_fin = nuevo_min_ini + duracion
                ev_copy["minuto_inicio"] = nuevo_min_ini
                ev_copy["minuto_fin"] = nuevo_min_fin
                ev_copy["hora_inicio_str"] = r.nueva_hora_inicio.strftime("%H:%M")
                fin_h = nuevo_min_fin // 60
                fin_m = nuevo_min_fin % 60
                ev_copy["hora_fin_str"] = f"{fin_h:02d}:{fin_m:02d}" if fin_h < 24 else "23:59"
                ev_copy["reubicada"] = True
                ev_copy["borde_clase"] = "border-2 border-[#0369A1]"
            else:
                ev_copy["reubicada"] = False
                ev_copy["borde_clase"] = "border-[#00CCFF] ring-1 ring-[#00CCFF]/50"
        eventos_procesados.append(ev_copy)

    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dias_resultado = []

    for idx, nombre_dia in enumerate(dias_nombres):
        dia_fecha = lunes + timedelta(days=idx)
        info_turno = obtener_turno_dia(dia_fecha, config=config)

        bloques_turno: list[dict[str, Any]] = []
        if not info_turno["es_descanso"] and info_turno["codigo"]:
            bloques_turno = generar_bloques_dia_turno(info_turno["codigo"], dia_fecha)

        # Hitos y clases de este día
        hitos_dia = [
            dict(ev)
            for ev in eventos_procesados
            if ev.get("fecha") == dia_fecha and ev.get("es_hito")
        ]
        clases_dia = [
            dict(ev)
            for ev in eventos_procesados
            if ev.get("fecha") == dia_fecha and not ev.get("es_hito")
        ]

        # Comprobar solapamientos entre clases y bloques de fábrica/bus
        for clase in clases_dia:
            clase.setdefault("tipo", "clase")
            clase["tiene_solapamiento"] = False
            clase["motivo_solapamiento"] = ""
            clase.setdefault("color_bg", "#E0F7FA")
            clase.setdefault("color_borde", "#00CCFF")
            clase.setdefault("color_texto", "#0E7490")
            if clase.get("reubicada"):
                clase["borde_clase"] = "border-2 border-[#0369A1]"
            else:
                clase["borde_clase"] = "border-[#00CCFF] ring-1 ring-[#00CCFF]/50"

            c_ini = clase["minuto_inicio"]
            c_fin = clase["minuto_fin"]

            for b in bloques_turno:
                b_ini = b["minuto_inicio"]
                b_fin = b["minuto_fin"]
                if max(c_ini, b_ini) < min(c_fin, b_fin):
                    clase["tiene_solapamiento"] = True
                    clase["motivo_solapamiento"] = (
                        f"Solapa con {b['titulo']} ({b['hora_inicio_str']}–{b['hora_fin_str']})"
                    )
                    b["tiene_solapamiento"] = True
                    b["motivo_solapamiento"] = (
                        f"Solapa con {clase.get('titulo', 'Clase')} ({clase['hora_inicio_str']}–{clase['hora_fin_str']})"
                    )

        # Privacidad para solicitantes (R5): fábrica, buses y clases se muestran como 'No disponible'
        if not es_gestor:
            for b in bloques_turno:
                b["titulo"] = "No disponible"
                b["tiene_solapamiento"] = False
                b["motivo_solapamiento"] = ""
            for c in clases_dia:
                c["titulo"] = "No disponible"
                c["tiene_solapamiento"] = False
                c["motivo_solapamiento"] = ""

        # Citas del día (R3, R4, R5)
        citas_bloques: list[dict[str, Any]] = []
        try:
            from turnos.models import Cita

            citas_qs = (
                Cita.objects.filter(fecha=dia_fecha)
                .exclude(estado="rechazada")
                .select_related("solicitante")
            )
            for cita in citas_qs:
                es_propia = (
                    (usuario == cita.solicitante)
                    if (usuario and getattr(usuario, "is_authenticated", False))
                    else False
                )

                # Si es solicitada y no es propia ni es gestor, no se dibuja a terceros
                if cita.estado == "solicitada" and not (es_propia or es_gestor):
                    continue

                c_ini = cita.hora_inicio.hour * 60 + cita.hora_inicio.minute
                c_fin = cita.hora_fin.hour * 60 + cita.hora_fin.minute
                duracion = max(c_fin - c_ini, 25)
                color = obtener_color_solicitante(cita.solicitante.username)
                mostrar_motivo = es_propia or es_gestor

                citas_bloques.append(
                    {
                        "tipo": "cita",
                        "id": f"cita-{cita.id}",
                        "cita_id": cita.id,
                        "titulo": f"Cita: {cita.solicitante.username}",
                        "solicitante": cita.solicitante.username,
                        "motivo": cita.motivo if mostrar_motivo else "",
                        "mostrar_motivo": mostrar_motivo,
                        "estado": cita.estado,
                        "hora_inicio_str": cita.hora_inicio.strftime("%H:%M"),
                        "hora_fin_str": cita.hora_fin.strftime("%H:%M"),
                        "minuto_inicio": c_ini,
                        "minuto_fin": c_fin,
                        "color_solicitante": color,
                        "color_borde": color,
                        "tiene_solapamiento": False,
                        "motivo_solapamiento": "",
                    }
                )
        except Exception:  # noqa: BLE001, S110
            pass

        # Combinar bloques y calcular posiciones CSS en píxeles y porcentajes
        todos_bloques = bloques_turno + clases_dia + citas_bloques
        for b in todos_bloques:
            duracion = max(b["minuto_fin"] - b["minuto_inicio"], 25)
            b["top_px"] = b["minuto_inicio"]
            b["height_px"] = duracion
            b["top_percent"] = round((b["minuto_inicio"] / 1440.0) * 100, 2)
            b["height_percent"] = round((duracion / 1440.0) * 100, 2)
            b["top_css"] = f"{(b['minuto_inicio'] / 1440.0) * 100:.2f}%"
            b["height_css"] = f"{(duracion / 1440.0) * 100:.2f}%"

        # Ordenar bloques cronológicamente
        todos_bloques.sort(key=lambda x: x["minuto_inicio"])

        dias_resultado.append(
            {
                "fecha": dia_fecha,
                "nombre_dia": nombre_dia,
                "numero_dia": dia_fecha.day,
                "mes": dia_fecha.strftime("%b"),
                "es_hoy": dia_fecha == hoy,
                "es_descanso": info_turno["es_descanso"],
                "codigo_turno": info_turno["codigo"],
                "nombre_turno": info_turno["nombre"],
                "color_turno": info_turno["color"],
                "fabrica": info_turno["fabrica"],
                "bus_ida": info_turno["bus_ida"],
                "bus_vuelta": info_turno["bus_vuelta"],
                "franja_libre": info_turno["franja_libre"],
                "franjas_disponibles": franjas_semana.get(dia_fecha, []),
                "hitos": hitos_dia,
                "bloques": todos_bloques,
            }
        )

    return dias_resultado


def obtener_semanas_calendario(
    fecha_referencia: date,
    num_semanas: int = 4,
    config: Any | None = None,
) -> list[list[dict[str, Any]]]:
    """Genera una lista de semanas (lunes a domingo) con la informacion de turnos para cada dia."""
    lunes_inicio = fecha_referencia - timedelta(days=fecha_referencia.weekday())
    semanas = []
    hoy = date.today()

    for s in range(num_semanas):
        dias_semana = []
        for d in range(7):
            dia = lunes_inicio + timedelta(days=s * 7 + d)
            info = obtener_turno_dia(dia, config=config)
            info["es_hoy"] = dia == hoy
            info["numero_dia"] = dia.day
            info["mes"] = dia.strftime("%b")
            dias_semana.append(info)
        semanas.append(dias_semana)

    return semanas
