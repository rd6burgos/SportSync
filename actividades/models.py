from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Actividad(models.Model):
    class Tipo(models.TextChoices):
        ACTIVIDAD = "actividad", "Actividad deportiva"
        TORNEO = "torneo", "Torneo individual"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADA = "publicada", "Publicada"
        INSCRIPCION_CERRADA = "inscripcion_cerrada", "Inscripción cerrada"
        EN_CURSO = "en_curso", "En curso"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    nombre = models.CharField(max_length=150)

    descripcion = models.TextField(
        "descripción",
        max_length=3000,
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.ACTIVIDAD,
    )

    deporte = models.CharField(max_length=100)

    ubicacion = models.CharField(
        "ubicación",
        max_length=250,
    )

    fecha_inicio = models.DateTimeField(
        "fecha y hora de inicio",
    )

    fecha_fin = models.DateTimeField(
        "fecha y hora de finalización",
    )

    cupo_maximo = models.PositiveIntegerField(
        "cupo máximo",
        validators=[MinValueValidator(1)],
    )

    costo = models.DecimalField(
        "costo de inscripción",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="actividades_organizadas",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "actividad"
        verbose_name_plural = "actividades"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(cupo_maximo__gte=1),
                name="actividad_cupo_mayor_cero",
            ),
            models.CheckConstraint(
                condition=models.Q(costo__gte=0),
                name="actividad_costo_no_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    fecha_fin__gt=models.F("fecha_inicio")
                ),
                name="actividad_fin_posterior_inicio",
            ),
        ]

    def clean(self):
        super().clean()

        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_fin <= self.fecha_inicio:
                raise ValidationError({
                    "fecha_fin": (
                        "La finalización debe ser posterior al inicio."
                    ),
                })

    def __str__(self):
        return self.nombre

    def transiciones_permitidas(self):
        transiciones = {
            self.Estado.BORRADOR: (
                self.Estado.PUBLICADA,
                self.Estado.CANCELADA,
            ),
            self.Estado.PUBLICADA: (
                self.Estado.INSCRIPCION_CERRADA,
                self.Estado.CANCELADA,
            ),
            self.Estado.INSCRIPCION_CERRADA: (
                self.Estado.EN_CURSO,
                self.Estado.CANCELADA,
            ),
            self.Estado.EN_CURSO: (
                self.Estado.FINALIZADA,
                self.Estado.CANCELADA,
            ),
            self.Estado.FINALIZADA: (),
            self.Estado.CANCELADA: (),
        }

        return transiciones.get(self.estado, ())

    def cambiar_estado(self, nuevo_estado):
        if nuevo_estado not in self.transiciones_permitidas():
            raise ValidationError(
                "No se permite ese cambio de estado."
            )

        ahora = timezone.now()

        if nuevo_estado == self.Estado.PUBLICADA:
            self.full_clean()

            if self.fecha_inicio <= ahora:
                raise ValidationError(
                    "Para publicar, la fecha de inicio debe ser futura."
                )

        if nuevo_estado == self.Estado.EN_CURSO:
            if ahora < self.fecha_inicio:
                raise ValidationError(
                    "No puedes iniciar la actividad antes "
                    "de su fecha y hora de inicio."
                )

        if nuevo_estado == self.Estado.FINALIZADA:
            if ahora < self.fecha_fin:
                raise ValidationError(
                    "No puedes finalizar la actividad antes "
                    "de su fecha y hora de finalización."
                )

        actualizadas = type(self).objects.filter(
            pk=self.pk,
            estado=self.estado,
        ).update(
            estado=nuevo_estado,
        )

        if actualizadas == 0:
            raise ValidationError(
                "La actividad cambió. Recarga la página e inténtalo de nuevo."
            )

        self.estado = nuevo_estado