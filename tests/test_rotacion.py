from datetime import date, timedelta

from turnos.rotacion import (
    HORARIOS_TURNOS,
    ORDEN_ROTACION,
    obtener_turno_dia,
)


def test_r1_rotacion_trisenamal_ciclo_a_c_b():
    """R1 (criterio portante): ciclo determinista de 21 dias A -> C -> B -> A."""
    fecha_base = date(2026, 10, 12)  # Lunes, Turno A
    turno_inicial = "A"

    assert ORDEN_ROTACION == ["A", "C", "B"]

    # Semanas 1 a 3 (dias 0 a 20): Turno A de lunes a viernes
    for sem in range(3):
        lunes = fecha_base + timedelta(days=sem * 7)
        viernes = lunes + timedelta(days=4)
        info_lunes = obtener_turno_dia(lunes, fecha_base=fecha_base, turno_inicial=turno_inicial)
        info_viernes = obtener_turno_dia(
            viernes, fecha_base=fecha_base, turno_inicial=turno_inicial
        )
        assert info_lunes["codigo"] == "A", f"R1: Semana {sem + 1} lunes debe ser Turno A"
        assert info_viernes["codigo"] == "A", f"R1: Semana {sem + 1} viernes debe ser Turno A"

    # Semanas 4 a 6 (dias 21 a 41): Turno C de lunes a viernes
    for sem in range(3, 6):
        lunes = fecha_base + timedelta(days=sem * 7)
        viernes = lunes + timedelta(days=4)
        info_lunes = obtener_turno_dia(lunes, fecha_base=fecha_base, turno_inicial=turno_inicial)
        info_viernes = obtener_turno_dia(
            viernes, fecha_base=fecha_base, turno_inicial=turno_inicial
        )
        assert info_lunes["codigo"] == "C", f"R1: Semana {sem + 1} lunes debe ser Turno C"
        assert info_viernes["codigo"] == "C", f"R1: Semana {sem + 1} viernes debe ser Turno C"

    # Semanas 7 a 9 (dias 42 a 62): Turno B de lunes a viernes
    for sem in range(6, 9):
        lunes = fecha_base + timedelta(days=sem * 7)
        viernes = lunes + timedelta(days=4)
        info_lunes = obtener_turno_dia(lunes, fecha_base=fecha_base, turno_inicial=turno_inicial)
        info_viernes = obtener_turno_dia(
            viernes, fecha_base=fecha_base, turno_inicial=turno_inicial
        )
        assert info_lunes["codigo"] == "B", f"R1: Semana {sem + 1} lunes debe ser Turno B"
        assert info_viernes["codigo"] == "B", f"R1: Semana {sem + 1} viernes debe ser Turno B"

    # Semana 10 (dia 63): Vuelve a Turno A
    lunes_sem10 = fecha_base + timedelta(days=63)
    info_sem10 = obtener_turno_dia(lunes_sem10, fecha_base=fecha_base, turno_inicial=turno_inicial)
    assert info_sem10["codigo"] == "A", "R1: Tras 63 dias debe volver al Turno A"


def test_r2_horarios_fijos_fabrica_y_buses():
    """R2: Horarios exactos de fabrica, bus ida/vuelta y franja libre."""
    horario_a = HORARIOS_TURNOS["A"]
    assert horario_a["fabrica"] == "05:45–13:45"
    assert horario_a["bus_ida"] == "05:00–05:45"
    assert horario_a["bus_vuelta"] == "14:00–15:30"
    assert horario_a["franja_libre"] == "15:35–19:45"

    horario_b = HORARIOS_TURNOS["B"]
    assert horario_b["fabrica"] == "13:45–21:45"
    assert horario_b["bus_ida"] == "13:00–13:45"
    assert horario_b["bus_vuelta"] == "22:00–23:30"
    assert horario_b["franja_libre"] == "08:00–12:30"

    horario_c = HORARIOS_TURNOS["C"]
    assert horario_c["fabrica"] == "21:45–05:45"
    assert horario_c["bus_ida"] == "21:00–21:45"
    assert horario_c["bus_vuelta"] == "06:00–07:30"
    assert horario_c["franja_libre"] == "15:30–20:15"


def test_r3_fines_de_semana_como_descanso():
    """R3: Sabados y domingos no tienen jornada y son descanso semanal."""
    sabado = date(2026, 10, 17)
    domingo = date(2026, 10, 18)

    info_sabado = obtener_turno_dia(sabado, fecha_base=date(2026, 10, 12), turno_inicial="A")
    info_domingo = obtener_turno_dia(domingo, fecha_base=date(2026, 10, 12), turno_inicial="A")

    assert info_sabado["es_descanso"] is True
    assert info_sabado["codigo"] is None
    assert "Descanso" in info_sabado["nombre"]

    assert info_domingo["es_descanso"] is True
    assert info_domingo["codigo"] is None
    assert "Descanso" in info_domingo["nombre"]
