import uuid

from django.conf import settings
from django.db import models


class Inscripcion(models.Model):

    class Estado(models.TextChoices):
        CONFIRMADA = "confirmada", "Confirmada"
        LISTA_ESPERA = "lista_espera", "Lista de espera"
        CANCELADA = "cancelada", "Cancelada"

    participante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inscripciones",
    )

    actividad = models.ForeignKey(
        "actividades.Actividad",
        on_delete=models.PROTECT,
        related_name="inscripciones",
    )

    estado = models.CharField(
        max_length=15,
        choices=Estado.choices,
        default=Estado.CONFIRMADA,
    )

    fecha_inscripcion = models.DateTimeField(auto_now_add=True)

    qr_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    class Meta:
        ordering = ["fecha_inscripcion"]
        verbose_name = "inscripción"
        verbose_name_plural = "inscripciones"
        constraints = [
            models.UniqueConstraint(
                fields=["participante", "actividad"],
                condition=~models.Q(estado="cancelada"),
                name="una_inscripcion_activa_por_actividad",
            ),
        ]

    def __str__(self):
        return f"{self.participante.email} → {self.actividad.nombre}"
    














class Notificacion(models.Model):
    """Registro de cada correo que el sistema debe enviar y de su resultado."""

    class Tipo(models.TextChoices):
        INSCRIPCION_CONFIRMADA = "inscripcion_confirmada", "Inscripción confirmada"
        LISTA_ESPERA = "lista_espera", "En lista de espera"
        PROMOCION = "promocion", "Promoción desde la lista de espera"
        ACTIVIDAD_EN_CURSO = "actividad_en_curso", "Actividad iniciada"
        ACTIVIDAD_FINALIZADA = "actividad_finalizada", "Actividad finalizada"
        ACTIVIDAD_CANCELADA = "actividad_cancelada", "Actividad cancelada"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ENVIADA = "enviada", "Enviada"
        FALLIDA = "fallida", "Fallida"

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notificaciones",
    )

    actividad = models.ForeignKey(
        "actividades.Actividad",
        on_delete=models.PROTECT,
        related_name="notificaciones",
    )

    # Se guarda el correo usado, por si el usuario lo cambia después.
    correo = models.EmailField()
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    asunto = models.CharField(max_length=200)

    mensaje = models.TextField()

    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    error = models.TextField(blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion", "-pk"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.correo} ({self.get_estado_display()})"