from datetime import date
from typing import ClassVar

from django.contrib.auth.models import User
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


class ReubicacionClase(models.Model):
    """Registro de reubicación de una clase universitaria solapada a un momento posterior."""

    configuracion = models.ForeignKey(
        ConfiguracionTurno,
        on_delete=models.CASCADE,
        related_name="reubicaciones",
        verbose_name="Configuración asociada",
    )
    uid_evento = models.CharField(
        max_length=255,
        verbose_name="UID del evento iCal",
    )
    fecha_original = models.DateField(
        verbose_name="Fecha original de la clase",
    )
    hora_inicio_original = models.TimeField(
        verbose_name="Hora de inicio original",
    )
    nueva_fecha = models.DateField(
        verbose_name="Nueva fecha asignada",
    )
    nueva_hora_inicio = models.TimeField(
        verbose_name="Nueva hora de inicio asignada",
    )
    creado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de reubicación",
    )

    class Meta:
        verbose_name = "Reubicación de clase"
        verbose_name_plural = "Reubicaciones de clases"
        unique_together = ("configuracion", "uid_evento", "fecha_original")

    def __str__(self) -> str:
        return (
            f"Reubicación {self.uid_evento} "
            f"({self.fecha_original} {self.hora_inicio_original} -> "
            f"{self.nueva_fecha} {self.nueva_hora_inicio})"
        )


class Cita(models.Model):
    """Reserva de cita de un compañero durante las franjas disponibles de Pau."""

    ESTADOS: ClassVar[list[tuple[str, str]]] = [
        ("solicitada", "Solicitada"),
        ("confirmada", "Confirmada"),
        ("contraoferta", "Contraoferta"),
        ("cancelada", "Cancelada"),
        ("rechazada", "Rechazada"),
        ("caducada", "Caducada"),
    ]

    solicitante = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="citas",
        verbose_name="Usuario solicitante",
    )
    fecha = models.DateField(
        verbose_name="Fecha de la cita",
    )
    hora_inicio = models.TimeField(
        verbose_name="Hora de inicio",
    )
    hora_fin = models.TimeField(
        verbose_name="Hora de fin",
    )
    motivo = models.CharField(
        max_length=250,
        verbose_name="Motivo de la cita",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="solicitada",
        verbose_name="Estado de la cita",
    )
    fecha_propuesta = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha propuesta (contraoferta)",
    )
    hora_inicio_propuesta = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Hora de inicio propuesta",
    )
    hora_fin_propuesta = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Hora de fin propuesta",
    )
    mensaje_contraoferta = models.CharField(
        max_length=250,
        blank=True,
        default="",
        verbose_name="Mensaje de contraoferta",
    )
    creado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering: ClassVar[list[str]] = ["fecha", "hora_inicio"]

    def __str__(self) -> str:
        return (
            f"Cita de {self.solicitante.username} "
            f"({self.fecha} {self.hora_inicio}–{self.hora_fin}) [{self.estado}]"
        )


class ActividadAutobus(models.Model):
    """Registro interactivo de actividades realizadas por Pau en trayectos de autobús pasados."""

    OPCIONES_BUS: ClassVar[list[tuple[str, str]]] = [
        ("bus_ida", "Autobús Ida"),
        ("bus_vuelta", "Autobús Vuelta"),
    ]

    fecha = models.DateField(
        verbose_name="Fecha del trayecto",
    )
    tipo_bus = models.CharField(
        max_length=20,
        choices=OPCIONES_BUS,
        verbose_name="Tipo de autobús",
    )
    actividades = models.JSONField(
        default=list,
        verbose_name="Actividades realizadas",
    )
    creado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro",
    )
    actualizado_el = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        verbose_name = "Actividad en autobús"
        verbose_name_plural = "Actividades en autobuses"
        unique_together = ("fecha", "tipo_bus")

    def __str__(self) -> str:
        return f"Actividades {self.tipo_bus} ({self.fecha}): {', '.join(self.actividades)}"


class FestivoParada(models.Model):
    """Registro de días festivos oficiales y paradas técnicas o vacaciones de fábrica."""

    fecha = models.DateField(
        unique=True,
        verbose_name="Fecha",
    )
    es_festivo = models.BooleanField(
        default=True,
        verbose_name="Es festivo o parada",
    )
    motivo = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Motivo o descripción",
    )
    es_oficial = models.BooleanField(
        default=False,
        verbose_name="Es festivo oficial",
    )
    creado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )
    actualizado_el = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        verbose_name = "Festivo o parada de fábrica"
        verbose_name_plural = "Festivos y paradas de fábrica"

    def __str__(self) -> str:
        estado = "Festivo" if self.es_festivo else "Laborable (revertido)"
        motivo_str = f" - {self.motivo}" if self.motivo else ""
        return f"{self.fecha}: {estado}{motivo_str}"


class ExcepcionTurnoSemana(models.Model):
    """Anulación puntual del turno asignado a toda una semana a partir de su lunes."""

    OPCIONES_TURNO: ClassVar[list[tuple[str, str]]] = [
        ("A", "Turno A (Mañana)"),
        ("B", "Turno B (Tarde)"),
        ("C", "Turno C (Noche)"),
    ]

    lunes_semana = models.DateField(
        unique=True,
        verbose_name="Lunes de la semana",
        help_text="Fecha del lunes que identifica la semana completa",
    )
    turno = models.CharField(
        max_length=1,
        choices=OPCIONES_TURNO,
        verbose_name="Turno semanal asignado",
    )
    creado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )
    actualizado_el = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        verbose_name = "Excepción de turno semanal"
        verbose_name_plural = "Excepciones de turno semanal"

    def __str__(self) -> str:
        return f"Semana {self.lunes_semana}: Turno {self.turno}"


class VigenciaRotacion(models.Model):
    """Punto de anclaje/inicio o restablecimiento de la rotación de turnos a partir de una fecha."""

    OPCIONES_TURNO: ClassVar[list[tuple[str, str]]] = [
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
    ]

    fecha_inicio = models.DateField(
        unique=True,
        db_index=True,
        verbose_name="Fecha de inicio de la vigencia",
    )
    turno_inicial = models.CharField(
        max_length=1,
        choices=OPCIONES_TURNO,
        verbose_name="Turno inicial",
    )
    creado_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )

    class Meta:
        verbose_name = "Vigencia de rotación"
        verbose_name_plural = "Vigencias de rotación"
        ordering: ClassVar[list[str]] = ["fecha_inicio"]

    def __str__(self) -> str:
        return f"Vigencia desde {self.fecha_inicio}: Turno {self.turno_inicial}"


