from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from actividades.models import Actividad

from .lista_espera import promover_lista_espera
from .models import Inscripcion, Pago
from .notificaciones import (
    notificar_pago_aprobado,
    notificar_pago_rechazado,
    notificar_promocion,
)


# Estados que el organizador puede asignar a un pago en persona.
ESTADOS_DEL_ORGANIZADOR = (
    Pago.Estado.EN_REVISION,
    Pago.Estado.APROBADO,
    Pago.Estado.RECHAZADO,
)

# Estados de la actividad en los que todavía tiene sentido gestionar pagos.
ESTADOS_ACTIVIDAD_GESTIONABLES = (
    Actividad.Estado.PUBLICADA,
    Actividad.Estado.INSCRIPCION_CERRADA,
    Actividad.Estado.EN_CURSO,
)


def crear_pago_si_corresponde(inscripcion):
    """Crea el pago pendiente si la actividad tiene costo. Si es gratuita, no."""

    actividad = inscripcion.actividad

    if actividad.costo > 0:
        return Pago.objects.create(inscripcion=inscripcion, monto=actividad.costo)

    return None


def cancelar_pago(inscripcion):
    """
    Marca el pago como cancelado cuando se cancela la inscripción.
    Si ya estaba aprobado, el reembolso se gestiona fuera del sistema.
    """
    Pago.objects.filter(
        inscripcion=inscripcion,
        estado__in=(
            Pago.Estado.PENDIENTE,
            Pago.Estado.EN_REVISION,
            Pago.Estado.APROBADO,
        ),
    ).update(estado=Pago.Estado.CANCELADO)


def resolver_pago(pago_id, nuevo_estado, revisor):
    """
    El organizador mueve un pago en persona: Pendiente -> En revisión ->
    Aprobado, o Rechazado (desde Pendiente o En revisión).

    Rechazar un pago cancela la inscripción y libera el cupo, que ocupa el
    primero de la lista de espera (CR-04).

    Lanza ValidationError con el motivo si la operación no es válida.

    """
    with transaction.atomic():
        # Mismo orden de bloqueo que al inscribirse o cancelar: primero la
        # actividad, luego lo demás.
        actividad_id = Pago.objects.values_list(
            "inscripcion__actividad_id", flat=True
        ).get(pk=pago_id)
        actividad = Actividad.objects.select_for_update().get(pk=actividad_id)
        pago = (
            Pago.objects.select_for_update()
            .select_related("inscripcion__participante", "inscripcion__actividad")
            .get(pk=pago_id)
        )
        inscripcion = pago.inscripcion

        if nuevo_estado not in ESTADOS_DEL_ORGANIZADOR:
            raise ValidationError("Ese estado no se puede asignar desde el panel.")

        if nuevo_estado not in pago.transiciones_permitidas():
            raise ValidationError(
                f"No se puede pasar un pago {pago.get_estado_display().lower()} "
                f"a {Pago.Estado(nuevo_estado).label.lower()}."
            )

        if inscripcion.estado != Inscripcion.Estado.CONFIRMADA:
            raise ValidationError(
                "La inscripción no está confirmada (está en lista de espera o "
                "fue cancelada), así que su pago no se puede gestionar."
            )

        if actividad.estado not in ESTADOS_ACTIVIDAD_GESTIONABLES:
            raise ValidationError(

                "La actividad ya finalizó o fue cancelada: no se pueden "
                "gestionar sus pagos."
            )

        ahora = timezone.now()

        pago.estado = nuevo_estado
        pago.revisado_por = revisor
        pago.fecha_revision = ahora

        if nuevo_estado in (Pago.Estado.EN_REVISION, Pago.Estado.APROBADO):
            pago.metodo = pago.metodo or Pago.Metodo.PRESENCIAL

        if nuevo_estado == Pago.Estado.APROBADO:
            pago.fecha_pago = ahora

        pago.save()

        if nuevo_estado == Pago.Estado.APROBADO:
            notificar_pago_aprobado(pago)

        elif nuevo_estado == Pago.Estado.RECHAZADO:
            inscripcion.estado = Inscripcion.Estado.CANCELADA
            inscripcion.save(update_fields=["estado"])

            notificar_pago_rechazado(pago)

            for promovida in promover_lista_espera(actividad):
                notificar_promocion(promovida)

    return pago