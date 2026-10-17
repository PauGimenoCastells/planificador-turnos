from datetime import date, timedelta
from typing import Any

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


def obtener_eventos_semana(
    fecha_lunes: date,
    config: Any | None = None,
    eventos_ical: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Calcula para los 7 días de la semana (Lunes a Domingo) sus bloques horarios y solapamientos."""
    lunes = fecha_lunes - timedelta(days=fecha_lunes.weekday())
    domingo = lunes + timedelta(days=6)
    hoy = date.today()

    if eventos_ical is None and config is not None and getattr(config, "contenido_ical_cache", ""):
        from turnos.ical import parsear_feed_ical

        eventos_ical = parsear_feed_ical(
            config.contenido_ical_cache,
            fecha_inicio=lunes,
            fecha_fin=domingo,
        )
    elif eventos_ical is None:
        eventos_ical = []

    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dias_resultado = []

    for idx, nombre_dia in enumerate(dias_nombres):
        dia_fecha = lunes + timedelta(days=idx)
        info_turno = obtener_turno_dia(dia_fecha, config=config)

        bloques_turno: list[dict[str, Any]] = []
        if not info_turno["es_descanso"] and info_turno["codigo"]:
            bloques_turno = generar_bloques_dia_turno(info_turno["codigo"], dia_fecha)

        # Clases de este día
        clases_dia = [dict(ev) for ev in eventos_ical if ev.get("fecha") == dia_fecha]

        # Comprobar solapamientos entre clases y bloques de fábrica/bus
        for clase in clases_dia:
            clase.setdefault("tipo", "clase")
            clase.setdefault("tiene_solapamiento", False)
            clase.setdefault("motivo_solapamiento", "")
            clase.setdefault("color_bg", "#E0F7FA")
            clase.setdefault("color_borde", "#00CCFF")
            clase.setdefault("color_texto", "#0E7490")

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

        # Combinar bloques y calcular porcentajes CSS
        todos_bloques = bloques_turno + clases_dia
        for b in todos_bloques:
            b["top_percent"] = round((b["minuto_inicio"] / 1440.0) * 100, 2)
            duracion = max(b["minuto_fin"] - b["minuto_inicio"], 25)
            b["height_percent"] = round((duracion / 1440.0) * 100, 2)

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
