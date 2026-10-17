import urllib.error
import urllib.request
import zoneinfo
from datetime import date, datetime, time, timedelta
from typing import Any

import icalendar
import recurring_ical_events

ZONA_MADRID = zoneinfo.ZoneInfo("Europe/Madrid")


def descargar_feed_ical(url: str, timeout: int = 15) -> str:
    """Descarga el contenido de un feed iCal (.ics) desde una URL remota."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/calendar,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        datos = response.read()
        try:
            return datos.decode("utf-8")
        except UnicodeDecodeError:
            return datos.decode("latin-1", errors="replace")


def parsear_feed_ical(
    contenido_ics: str,
    fecha_inicio: date,
    fecha_fin: date,
) -> list[dict[str, Any]]:
    """
    Parsea una cadena iCalendar (.ics), expandiendo recurrencias (RRULE)
    y extrayendo los eventos comprendidos entre fecha_inicio y fecha_fin en Europe/Madrid.
    """
    if not contenido_ics or not contenido_ics.strip():
        return []

    try:
        cal = icalendar.Calendar.from_ical(contenido_ics)
    except Exception:  # noqa: BLE001 - protección ante archivos ICS externos malformados
        return []

    # recurring_ical_events between acepta datetime o tuplas (YYYY, MM, DD)
    # Cubrimos desde el inicio de fecha_inicio hasta el final de fecha_fin
    dt_inicio = datetime.combine(fecha_inicio, time.min, tzinfo=ZONA_MADRID)
    dt_fin = datetime.combine(fecha_fin + timedelta(days=1), time.min, tzinfo=ZONA_MADRID)

    try:
        eventos_recur = recurring_ical_events.of(cal).between(dt_inicio, dt_fin)
    except Exception:  # noqa: BLE001 - fallback si recurring_ical_events falla por formatos no estándar
        eventos_recur = []
        for componente in cal.walk():
            if componente.name == "VEVENT":
                eventos_recur.append(componente)

    eventos_procesados: list[dict[str, Any]] = []

    for ev in eventos_recur:
        if ev.name != "VEVENT":
            continue

        resumen = str(ev.get("SUMMARY", "Clase"))
        descripcion = str(ev.get("DESCRIPTION", ""))
        ubicacion = str(ev.get("LOCATION", ""))

        dtstart_prop = ev.get("DTSTART")
        if not dtstart_prop:
            continue
        dtstart_val = dtstart_prop.dt

        es_hito = False
        # Si es solo date (todo el día), tratar como hito/evento del día
        if isinstance(dtstart_val, date) and not isinstance(dtstart_val, datetime):
            es_hito = True
            dt_inicio_local = datetime.combine(dtstart_val, time(9, 0), tzinfo=ZONA_MADRID)
            dt_fin_local = datetime.combine(dtstart_val, time(10, 0), tzinfo=ZONA_MADRID)
        else:
            if dtstart_val.tzinfo is None:
                dt_inicio_local = dtstart_val.replace(tzinfo=ZONA_MADRID)
            else:
                dt_inicio_local = dtstart_val.astimezone(ZONA_MADRID)

            dtend_prop = ev.get("DTEND")
            if dtend_prop:
                dtend_val = dtend_prop.dt
                if isinstance(dtend_val, date) and not isinstance(dtend_val, datetime):
                    dt_fin_local = datetime.combine(dtend_val, time(10, 0), tzinfo=ZONA_MADRID)
                    es_hito = True
                else:
                    if dtend_val == dtstart_val:
                        es_hito = True
                    if dtend_val.tzinfo is None:
                        dt_fin_local = dtend_val.replace(tzinfo=ZONA_MADRID)
                    else:
                        dt_fin_local = dtend_val.astimezone(ZONA_MADRID)
            else:
                dt_fin_local = dt_inicio_local + timedelta(hours=2)

        ev_fecha = dt_inicio_local.date()
        if ev_fecha < fecha_inicio or ev_fecha > fecha_fin:
            continue

        minuto_inicio = dt_inicio_local.hour * 60 + dt_inicio_local.minute
        minuto_fin = dt_fin_local.hour * 60 + dt_fin_local.minute
        if minuto_fin <= minuto_inicio:
            minuto_fin = min(minuto_inicio + 60, 24 * 60)
            fin_h = minuto_fin // 60
            fin_m = minuto_fin % 60
            hora_fin_str = f"{fin_h:02d}:{fin_m:02d}" if fin_h < 24 else "23:59"
        else:
            hora_fin_str = dt_fin_local.strftime("%H:%M")

        eventos_procesados.append(
            {
                "id": str(ev.get("UID", f"clase-{len(eventos_procesados)}")),
                "tipo": "hito" if es_hito else "clase",
                "es_hito": es_hito,
                "titulo": resumen,
                "descripcion": descripcion,
                "ubicacion": ubicacion,
                "fecha": ev_fecha,
                "hora_inicio_str": dt_inicio_local.strftime("%H:%M"),
                "hora_fin_str": hora_fin_str,
                "minuto_inicio": minuto_inicio,
                "minuto_fin": minuto_fin,
                "tiene_solapamiento": False,
                "motivo_solapamiento": "",
            }
        )

    # Ordenar por fecha y hora de inicio
    eventos_procesados.sort(key=lambda x: (x["fecha"], x["minuto_inicio"]))
    return eventos_procesados
