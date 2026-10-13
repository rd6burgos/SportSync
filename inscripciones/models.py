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