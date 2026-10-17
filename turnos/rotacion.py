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


def obtener_semanas_calendario(
    fecha_referencia: date,
    num_semanas: int = 4,
    config: Any | None = None,
) -> list[list[dict[str, Any]]]:
    """Genera una lista de semanas (lunes a domingo) con la informacion de turnos para cada dia."""
    # Encuentra el lunes de la semana de referencia
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
