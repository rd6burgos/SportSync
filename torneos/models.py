from django.conf import settings
from django.db import models


class Partido(models.Model):
    """Partido entre dos participantes de un torneo individual (CR-07)."""

    class Estado(models.TextChoices):
        PROGRAMADO = "programado", "Programado"
        JUGADO = "jugado", "Jugado"
        CANCELADO = "cancelado", "Cancelado"

    torneo = models.ForeignKey(
        "actividades.Actividad",
        on_delete=models.PROTECT,
        related_name="partidos",
        limit_choices_to={"tipo": "torneo"},
    )

    participante_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partidos_como_a",
    )

    participante_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partidos_como_b",
    )

    ronda = models.CharField(max_length=50, blank=True)
    fecha_hora = models.DateTimeField("fecha y hora")

    estado = models.CharField(
        max_length=15,
        choices=Estado.choices,
        default=Estado.PROGRAMADO,
    )

    # Resultado: ambos marcadores o ninguno.
    marcador_a = models.PositiveSmallIntegerField(null=True, blank=True)
    marcador_b = models.PositiveSmallIntegerField(null=True, blank=True)

    # Trazabilidad del resultado: quién lo registró (o corrigió) y cuándo.
    resultado_registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultados_registrados",
    )
    fecha_resultado = models.DateTimeField(null=True, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_hora", "pk"]
        verbose_name = "partido"
        verbose_name_plural = "partidos"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(participante_a=models.F("participante_b")),
                name="partido_participantes_distintos",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(marcador_a__isnull=True, marcador_b__isnull=True)
                    | models.Q(marcador_a__isnull=False, marcador_b__isnull=False)
                ),
                name="partido_marcadores_completos",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(estado="jugado")
                    | models.Q(marcador_a__isnull=False)
                ),
                name="partido_jugado_tiene_marcador",
            ),
        ]

    def __str__(self):
        return f"{self.participante_a} vs {self.participante_b} · {self.torneo}"

    @property
    def ganador(self):
        """El ganador, o None si no se ha jugado o fue empate."""
        if self.estado != self.Estado.JUGADO or self.marcador_a == self.marcador_b:
            return None

        return self.participante_a if self.marcador_a > self.marcador_b else self.participante_b