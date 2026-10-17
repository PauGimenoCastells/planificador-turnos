from datetime import date
from typing import ClassVar

from django.db import models


class ConfiguracionTurno(models.Model):
    """Configuracion de fecha base y turno inicial para la rotacion tri-semanal."""

    OPCIONES_TURNO: ClassVar[list[tuple[str, str]]] = [
        ("A", "Turno A (Mañana)"),
        ("B", "Turno B (Tarde)"),
        ("C", "Turno C (Noche)"),
    ]

    fecha_base = models.DateField(
        default=date(2026, 10, 12),
        verbose_name="Fecha base del ciclo",
        help_text="Fecha de referencia donde comienza el turno inicial seleccionado",
    )
    turno_inicial = models.CharField(
        max_length=1,
        choices=OPCIONES_TURNO,
        default="A",
        verbose_name="Turno inicial",
        help_text="Turno asignado en la fecha base",
    )
    url_ical_uni = models.URLField(
        blank=True,
        default="",
        verbose_name="URL del calendario iCal universitario",
        help_text="Enlace .ics de suscripción al calendario académico",
    )
    contenido_ical_cache = models.TextField(
        blank=True,
        default="",
        verbose_name="Caché de contenido iCal",
    )
    sincronizado_el = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última sincronización iCal",
    )
    actualizado_el = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        verbose_name = "Configuración de turno"
        verbose_name_plural = "Configuraciones de turnos"

    def __str__(self) -> str:
        return f"Configuración: Base {self.fecha_base} - Turno {self.turno_inicial}"

    @classmethod
    def obtener_activa(cls) -> "ConfiguracionTurno":
        """Obtiene la configuracion activa existente o crea la predeterminada."""
        config = cls.objects.first()
        if not config:
            config = cls.objects.create(fecha_base=date(2026, 10, 12), turno_inicial="A")
        return config
