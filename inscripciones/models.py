import uuid

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
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

    @property
    def pago_actual(self):
        """El pago de esta inscripción, o None si la actividad es gratuita."""
        try:
            return self.pago
        except ObjectDoesNotExist:
            return None

    @property

    def qr_habilitado(self):
        """
        El QR solo vale si la inscripción está confirmada y, en actividades
        de pago, el pago fue aprobado.
        """
        if self.estado != self.Estado.CONFIRMADA:
            return False

        pago = self.pago_actual

        return pago is None or pago.estado == Pago.Estado.APROBADO





















class Pago(models.Model):
    """Estado de pago de una inscripción en una actividad con costo (CR-12)."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_REVISION = "en_revision", "En revisión"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"
        CANCELADO = "cancelado", "Cancelado"

    class Metodo(models.TextChoices):
        PRESENCIAL = "presencial", "En persona"
        PAYPAL = "paypal", "PayPal"

    inscripcion = models.OneToOneField(
        Inscripcion,
        on_delete=models.PROTECT,
        related_name="pago",
    )


    # Copia del costo al momento de inscribirse.
    monto = models.DecimalField(max_digits=8, decimal_places=2)

    estado = models.CharField(
        max_length=15,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )

    metodo = models.CharField(max_length=15, choices=Metodo.choices, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_pago = models.DateTimeField(null=True, blank=True)

    # Quién revisó el pago (en persona) y cuándo.
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagos_revisados",
    )
    fecha_revision = models.DateTimeField(null=True, blank=True)

    # Datos de PayPal (se usan en la parte de pagos digitales).
    paypal_order_id = models.CharField(
        max_length=50, null=True, blank=True, unique=True
    )
    paypal_capture_id = models.CharField(max_length=50, blank=True)











    class Meta:

        ordering = ["-fecha_creacion", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(monto__gt=0),
                name="pago_monto_positivo",
            ),
        ]

    def __str__(self):
        return f"{self.inscripcion} · ${self.monto} · {self.get_estado_display()}"

    def transiciones_permitidas(self):
        transiciones = {
            self.Estado.PENDIENTE: (
                self.Estado.EN_REVISION,
                self.Estado.RECHAZADO,
                self.Estado.CANCELADO,
            ),
            self.Estado.EN_REVISION: (
                self.Estado.APROBADO,
                self.Estado.RECHAZADO,
                self.Estado.CANCELADO,
            ),
            self.Estado.APROBADO: (self.Estado.CANCELADO,),
            self.Estado.RECHAZADO: (),
            self.Estado.CANCELADO: (),
        }

        return transiciones.get(self.estado, ())





















class Notificacion(models.Model):

    """Registro de cada correo que el sistema debe enviar y de su resultado."""

    class Tipo(models.TextChoices):
        INSCRIPCION_CONFIRMADA = "inscripcion_confirmada", "Inscripción confirmada"
        LISTA_ESPERA = "lista_espera", "En lista de espera"
        PROMOCION = "promocion", "Promoción desde la lista de espera"
        ACTIVIDAD_EN_CURSO = "actividad_en_curso", "Actividad iniciada"
        ACTIVIDAD_FINALIZADA = "actividad_finalizada", "Actividad finalizada"
        ACTIVIDAD_CANCELADA = "actividad_cancelada", "Actividad cancelada"
        PAGO_APROBADO = "pago_aprobado", "Pago aprobado"
        PAGO_RECHAZADO = "pago_rechazado", "Pago rechazado"

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