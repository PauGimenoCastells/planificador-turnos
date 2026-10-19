import calendar
from datetime import date, datetime, time, timedelta
from typing import Any

from django.utils import timezone

ACTIVIDADES_CATALOGO_INFO = {
    "siesta": {"codigo": "siesta", "label": "Siesta", "emoji": "😴", "badge": "😴 Siesta"},
    "lectura": {"codigo": "lectura", "label": "Lectura", "emoji": "📖", "badge": "📖 Lectura"},
    "reflexion": {
        "codigo": "reflexion",
        "label": "Reflexión",
        "emoji": "🧠",
        "badge": "🧠 Reflexión",
    },
    "videojuegos": {
        "codigo": "videojuegos",
        "label": "Videojuegos",
        "emoji": "🎮",
        "badge": "🎮 Videojuegos",
    },
    "videos": {"codigo": "videos", "label": "Vídeos", "emoji": "🎬", "badge": "🎬 Vídeos"},
}

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

FESTIVOS_OFICIALES_MARTORELL_2026: dict[date, str] = {
    date(2026, 1, 1): "Año Nuevo",
    date(2026, 1, 6): "Epifanía del Señor",
    date(2026, 4, 3): "Viernes Santo",
    date(2026, 4, 6): "Lunes de Pascua",
    date(2026, 4, 27): "Festa del Sant Crist (Martorell)",
    date(2026, 5, 1): "Fiesta del Trabajo",
    date(2026, 5, 25): "Segona Pasqua (Martorell)",
    date(2026, 6, 24): "Sant Joan",
    date(2026, 8, 15): "Asunción de la Virgen",
    date(2026, 9, 11): "Diada Nacional de Catalunya",
    date(2026, 10, 12): "Fiesta Nacional de España",
    date(2026, 12, 8): "Inmaculada Concepción",
    date(2026, 12, 25): "Navidad",
    date(2026, 12, 26): "Sant Esteve",
}


def consultar_festivo_dia(fecha: date) -> dict[str, Any] | None:
    """
    Determina si una fecha es festivo o parada de fábrica (R1, R3).
    Cruza los registros de base de datos FestivoParada (que mandan sobre el catálogo)
    con el catálogo canónico de 14 festivos oficiales de Martorell 2026.
    """
    try:
        from turnos.models import FestivoParada

        fp = FestivoParada.objects.filter(fecha=fecha).first()
        if fp is not None:
            return {
                "es_festivo": fp.es_festivo,
                "motivo": fp.motivo or ("Festivo oficial" if fp.es_oficial else "Parada de fábrica"),
                "es_oficial": fp.es_oficial,
                "modificado_manualmente": True,
            }
    except Exception:  # noqa: BLE001, S110
        pass

    if fecha in FESTIVOS_OFICIALES_MARTORELL_2026:
        return {
            "es_festivo": True,
            "motivo": FESTIVOS_OFICIALES_MARTORELL_2026[fecha],
            "es_oficial": True,
            "modificado_manualmente": False,
        }

    return None


def obtener_turno_dia(
    fecha: date,
    fecha_base: date | None = None,
    turno_inicial: str = "A",
    config: Any | None = None,
) -> dict[str, Any]:
    """Calcula el turno correspondiente a una fecha segun el ciclo determinista de 21 dias y festivos."""
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
            "es_festivo": False,
            "nombre_festivo": None,
            "motivo": None,
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

    # Festivo o parada de fábrica (R1, R3, R4)
    info_festivo = consultar_festivo_dia(fecha)
    if info_festivo and info_festivo.get("es_festivo"):
        motivo = info_festivo.get("motivo") or "Festivo / Parada"
        return {
            "fecha": fecha,
            "es_descanso": False,
            "es_festivo": True,
            "es_oficial": info_festivo.get("es_oficial", False),
            "nombre_festivo": motivo,
            "motivo": motivo,
            "codigo": codigo,
            "nombre": motivo,
            "color": "#8B5CF6",
            "fabrica": None,
            "bus_ida": None,
            "bus_vuelta": None,
            "franja_libre": "Día completo",
        }

    return {
        "fecha": fecha,
        "es_descanso": False,
        "es_festivo": False,
        "nombre_festivo": None,
        "motivo": None,
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


def calcular_subdivision_citas(citas_bloques: list[dict[str, Any]]) -> None:
    """Calcula la subdivisión y posicionamiento visual de citas concurrentes solapadas:

    - 1 cita: ancho completo normal.
    - 2 citas: división vertical (50% ancho cada una).
    - 3 citas: división vertical en 3 columnas (33.3% ancho cada una).
    - 4 citas: cuadrícula 2x2 (50% ancho x 50% alto).
    - >4 citas: división en N columnas.
    """
    if not citas_bloques:
        return

    citas_ordenadas = sorted(citas_bloques, key=lambda c: (c["minuto_inicio"], c["minuto_fin"]))
    clusters: list[list[dict[str, Any]]] = []

    for cita in citas_ordenadas:
        agregada = False
        for cluster in clusters:
            if any(
                max(cita["minuto_inicio"], c["minuto_inicio"])
                < min(cita["minuto_fin"], c["minuto_fin"])
                for c in cluster
            ):
                cluster.append(cita)
                agregada = True
                break
        if not agregada:
            clusters.append([cita])

    merged_clusters: list[list[dict[str, Any]]] = []
    for cluster in clusters:
        fusionado = False
        for mc in merged_clusters:
            if any(
                max(c1["minuto_inicio"], c2["minuto_inicio"])
                < min(c1["minuto_fin"], c2["minuto_fin"])
                for c1 in cluster
                for c2 in mc
            ):
                mc.extend([c for c in cluster if c not in mc])
                fusionado = True
                break
        if not fusionado:
            merged_clusters.append(cluster)

    for cluster in merged_clusters:
        n = len(cluster)
        cluster.sort(key=lambda c: (c["minuto_inicio"], c["solicitante"]))
        if n == 1:
            c = cluster[0]
            c["layout_modo"] = "normal"
            c["posicion_css"] = "left: 4px; right: 4px;"
        elif n == 2:
            c0, c1 = cluster[0], cluster[1]
            c0["layout_modo"] = "col-2"
            c0["posicion_css"] = "left: 4px; width: calc(50% - 6px);"
            c1["layout_modo"] = "col-2"
            c1["posicion_css"] = "left: calc(50% + 2px); width: calc(50% - 6px);"
        elif n == 3:
            for idx, c in enumerate(cluster):
                c["layout_modo"] = "col-3"
                if idx == 0:
                    c["posicion_css"] = "left: 4px; width: calc(33.333% - 5px);"
                elif idx == 1:
                    c["posicion_css"] = "left: calc(33.333% + 2px); width: calc(33.333% - 5px);"
                else:
                    c["posicion_css"] = "left: calc(66.666% + 2px); width: calc(33.333% - 5px);"
        elif n == 4:
            cluster_ini = min(c["minuto_inicio"] for c in cluster)
            cluster_fin = max(c["minuto_fin"] for c in cluster)
            cluster_dur = max(cluster_fin - cluster_ini, 50)
            mitad_h = cluster_dur // 2
            for idx, c in enumerate(cluster):
                c["layout_modo"] = "grid-2x2"
                col = idx % 2
                row = idx // 2
                top = cluster_ini + (row * mitad_h)
                height = mitad_h - 2
                c["top_px"] = top
                c["height_px"] = height
                if col == 0:
                    c["posicion_css"] = (
                        f"left: 4px; width: calc(50% - 6px); top: {top}px; height: {height}px;"
                    )
                else:
                    c["posicion_css"] = (
                        f"left: calc(50% + 2px); width: calc(50% - 6px); top: {top}px; height: {height}px;"
                    )
        else:
            w = 100.0 / n
            for idx, c in enumerate(cluster):
                c["layout_modo"] = f"col-{n}"
                c["posicion_css"] = (
                    f"left: calc({idx * w:.2f}% + 2px); width: calc({w:.2f}% - 4px);"
                )


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

    fin_semana = lunes + timedelta(days=6)
    actividades_bus_map: dict[tuple[date, str], list[str]] = {}
    try:
        from turnos.models import ActividadAutobus

        for act in ActividadAutobus.objects.filter(fecha__gte=lunes, fecha__lte=fin_semana):
            actividades_bus_map[(act.fecha, act.tipo_bus)] = act.actividades
    except Exception:  # noqa: BLE001, S110
        pass

    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dias_resultado = []

    for idx, nombre_dia in enumerate(dias_nombres):
        dia_fecha = lunes + timedelta(days=idx)
        info_turno = obtener_turno_dia(dia_fecha, config=config)

        bloques_turno: list[dict[str, Any]] = []
        if not info_turno["es_descanso"] and info_turno["codigo"]:
            bloques_turno = generar_bloques_dia_turno(info_turno["codigo"], dia_fecha)

        ahora = timezone.now()
        for b in bloques_turno:
            if b.get("tipo") in ("bus_ida", "bus_vuelta"):
                b["fecha"] = dia_fecha
                acts = actividades_bus_map.get((dia_fecha, b["tipo"]), [])
                b["actividades"] = acts
                b["actividades_detalle"] = [
                    ACTIVIDADES_CATALOGO_INFO[a] for a in acts if a in ACTIVIDADES_CATALOGO_INFO
                ]
                h_fin_str = b["hora_fin_str"]
                if h_fin_str == "24:00":
                    hora_fin = time(23, 59, 59)
                else:
                    hora_fin = time.fromisoformat(h_fin_str)
                fin_dt = datetime.combine(dia_fecha, hora_fin)
                if timezone.is_naive(fin_dt):
                    fin_dt = timezone.make_aware(fin_dt, timezone.get_current_timezone())
                b["ha_pasado"] = fin_dt <= ahora

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

            # R6: Si no solapa con fábrica/bus, pero cae fuera de la franja disponible base del turno de Pau
            if not clase["tiene_solapamiento"]:
                if dia_fecha.weekday() in (5, 6):
                    base_ini, base_fin = 480, 1320  # 08:00 - 22:00
                elif info_turno["codigo"] == "A":
                    base_ini, base_fin = 935, 1185  # 15:35 - 19:45
                elif info_turno["codigo"] == "B":
                    base_ini, base_fin = 480, 750  # 08:00 - 12:30
                elif info_turno["codigo"] == "C":
                    base_ini, base_fin = 930, 1215  # 15:30 - 20:15
                else:
                    base_ini, base_fin = 0, 0

                if not (c_ini >= base_ini and c_fin <= base_fin):
                    clase["tiene_solapamiento"] = True
                    clase["motivo_solapamiento"] = (
                        "Conflicto: fuera de franja de disponibilidad (descanso de turno)"
                    )

        # Privacidad para solicitantes (R5): fábrica, buses y clases se muestran como 'No disponible'
        if not es_gestor:
            for b in bloques_turno:
                b["titulo"] = "No disponible"
                b["tiene_solapamiento"] = False
                b["motivo_solapamiento"] = ""
                b["actividades"] = []
                b["actividades_detalle"] = []
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
                .exclude(estado__in=["rechazada", "caducada", "cancelada"])
                .select_related("solicitante")
            )
            for cita in citas_qs:
                es_propia = (
                    (usuario == cita.solicitante)
                    if (usuario and getattr(usuario, "is_authenticated", False))
                    else False
                )

                # Si es solicitada o contraoferta y no es propia ni es gestor, no se dibuja a terceros
                if cita.estado in ("solicitada", "contraoferta") and not (es_propia or es_gestor):
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
                        "fecha_propuesta": cita.fecha_propuesta,
                        "hora_inicio_propuesta_str": (
                            cita.hora_inicio_propuesta.strftime("%H:%M")
                            if cita.hora_inicio_propuesta
                            else ""
                        ),
                        "hora_fin_propuesta_str": (
                            cita.hora_fin_propuesta.strftime("%H:%M")
                            if cita.hora_fin_propuesta
                            else ""
                        ),
                        "mensaje_contraoferta": (
                            cita.mensaje_contraoferta if mostrar_motivo else ""
                        ),
                        "es_propia": es_propia,
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

            calcular_subdivision_citas(citas_bloques)
        except Exception:  # noqa: BLE001, S110
            pass

        # Combinar bloques y calcular posiciones CSS en píxeles y porcentajes
        todos_bloques = bloques_turno + clases_dia + citas_bloques
        for b in todos_bloques:
            duracion = max(b["minuto_fin"] - b["minuto_inicio"], 25)
            if b.get("layout_modo") != "grid-2x2":
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
                "es_festivo": info_turno.get("es_festivo", False),
                "nombre_festivo": info_turno.get("nombre_festivo") or "",
                "motivo_festivo": info_turno.get("motivo") or "",
                "es_oficial": info_turno.get("es_oficial", False),
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


def formatear_duracion(minutos: int) -> str:
    """Formatea minutos a formato legible, ej: '3h', '2h 15m', '45m', '0m'."""
    if minutos <= 0:
        return "0m"
    horas = minutos // 60
    resto = minutos % 60
    if horas > 0 and resto > 0:
        return f"{horas}h {resto}m"
    elif horas > 0:
        return f"{horas}h"
    else:
        return f"{resto}m"


def calcular_metricas_autobus(
    dias_o_fecha: Any, config: Any | None = None
) -> dict[str, Any]:
    """Calcula las métricas de aprovechamiento de autobús (total y desglose por actividad).

    Acepta una lista de días (dias_semana) o una fecha de inicio de semana (lunes).
    Computa las horas y minutos acumulados en los trayectos de autobús (bus_ida y bus_vuelta)
    que tienen actividades registradas en la semana visible.
    """
    if isinstance(dias_o_fecha, (date, datetime)):
        dias_semana = obtener_eventos_semana(fecha_lunes=dias_o_fecha, config=config)
    elif isinstance(dias_o_fecha, list):
        dias_semana = dias_o_fecha
    else:
        dias_semana = []

    codigos_actividades = ["siesta", "lectura", "reflexion", "videojuegos", "videos"]
    desglose = {
        cod: {
            "codigo": cod,
            "label": ACTIVIDADES_CATALOGO_INFO[cod]["label"],
            "emoji": ACTIVIDADES_CATALOGO_INFO[cod]["emoji"],
            "badge": ACTIVIDADES_CATALOGO_INFO[cod]["badge"],
            "minutos": 0,
            "tiempo_formateado": "0m",
            "contador": 0,
        }
        for cod in codigos_actividades
    }

    total_minutos = 0
    total_trayectos = 0

    for dia in dias_semana:
        for b in dia.get("bloques", []):
            if b.get("tipo") in ("bus_ida", "bus_vuelta"):
                acts = b.get("actividades", [])
                if acts:
                    min_ini = b.get("minuto_inicio")
                    min_fin = b.get("minuto_fin")
                    if min_ini is not None and min_fin is not None and min_fin > min_ini:
                        duracion = min_fin - min_ini
                    else:
                        duracion = 0
                    acts_validas = [act for act in acts if act in desglose]
                    if duracion > 0 and acts_validas:
                        total_minutos += duracion
                        total_trayectos += 1
                        min_por_actividad = duracion / len(acts_validas)
                        for act in acts_validas:
                            desglose[act]["minutos"] += min_por_actividad
                            desglose[act]["contador"] += 1

    for cod in codigos_actividades:
        minutos_redondeados = round(desglose[cod]["minutos"])
        desglose[cod]["minutos"] = minutos_redondeados
        desglose[cod]["tiempo_formateado"] = formatear_duracion(minutos_redondeados)

    return {
        "total_minutos": total_minutos,
        "total_formateado": formatear_duracion(total_minutos),
        "total_horas": round(total_minutos / 60.0, 2),
        "total_trayectos": total_trayectos,
        "por_actividad": desglose,
        "desglose": list(desglose.values()),
        "siesta": desglose["siesta"],
        "lectura": desglose["lectura"],
        "reflexion": desglose["reflexion"],
        "videojuegos": desglose["videojuegos"],
        "videos": desglose["videos"],
    }


def obtener_semanas_calendario(
    fecha_referencia: date,
    num_semanas: int | None = None,
    config: Any | None = None,
) -> list[list[dict[str, Any]]]:
    """Genera una lista de semanas (lunes a domingo) con la informacion de turnos para cada dia del mes."""
    primer_dia_mes = date(fecha_referencia.year, fecha_referencia.month, 1)
    lunes_inicio = primer_dia_mes - timedelta(days=primer_dia_mes.weekday())

    if num_semanas is None:
        ultimo_dia_num = calendar.monthrange(fecha_referencia.year, fecha_referencia.month)[1]
        ultimo_dia_mes = date(fecha_referencia.year, fecha_referencia.month, ultimo_dia_num)
        dias_totales = (ultimo_dia_mes - lunes_inicio).days + 1
        num_semanas = max(4, (dias_totales + 6) // 7)

    semanas = []
    hoy = date.today()

    citas_por_dia: dict[date, list[Any]] = {}
    try:
        from turnos.models import Cita

        fin_semanas = lunes_inicio + timedelta(days=num_semanas * 7)
        citas_qs = (
            Cita.objects.filter(fecha__gte=lunes_inicio, fecha__lte=fin_semanas)
            .exclude(estado__in=["rechazada", "caducada"])
            .select_related("solicitante")
        )
        for c in citas_qs:
            citas_por_dia.setdefault(c.fecha, []).append(c)
    except Exception:  # noqa: BLE001, S110
        pass

    for s in range(num_semanas):
        dias_semana = []
        for d in range(7):
            dia = lunes_inicio + timedelta(days=s * 7 + d)
            info = obtener_turno_dia(dia, config=config)
            info["fecha"] = dia
            info["es_hoy"] = dia == hoy
            info["numero_dia"] = dia.day
            info["mes"] = dia.strftime("%b")
            info["mismo_mes"] = dia.month == fecha_referencia.month
            citas_dia = citas_por_dia.get(dia, [])
            info["citas"] = citas_dia
            info["total_citas"] = len(citas_dia)
            dias_semana.append(info)
        semanas.append(dias_semana)

    return semanas
