from django.utils import timezone

from actividades.models import Actividad

from .models import Inscripcion


# Una actividad cancelada o finalizada ya no ocupa el horario del participante.
ESTADOS_SIN_CONFLICTO = (
    Actividad.Estado.CANCELADA,
    Actividad.Estado.FINALIZADA,
)


def inscripciones_activas(participante):
    """Inscripciones del participante que todavía cuentan (no canceladas)."""
    return Inscripcion.objects.filter(participante=participante).exclude(
        estado=Inscripcion.Estado.CANCELADA
    )


def esta_inscrito(participante, actividad):
    """True si el participante ya tiene una inscripción activa en la actividad."""
    return inscripciones_activas(participante).filter(actividad=actividad).exists()


def conflicto_de_horario(participante, actividad):
    """
    Devuelve la inscripción activa del participante cuya actividad se solapa
    con `actividad`, o None si no hay conflicto.

    Dos actividades se solapan cuando cada una empieza antes de que termine

    la otra. Con desigualdades estrictas, si una termina justo cuando empieza
    la otra NO hay conflicto.
    """
    return (
        inscripciones_activas(participante)
        .exclude(actividad=actividad)
        .exclude(actividad__estado__in=ESTADOS_SIN_CONFLICTO)
        .filter(
            actividad__fecha_inicio__lt=actividad.fecha_fin,
            actividad__fecha_fin__gt=actividad.fecha_inicio,
        )
        .select_related("actividad")
        .order_by("actividad__fecha_inicio")
        .first()
    )


def _formato(fecha):
    return timezone.localtime(fecha).strftime("%d/%m/%Y %H:%M")


def motivo_de_rechazo(participante, actividad):
    """
    Revisa las reglas de la inscripción (menos el cupo, que se trata aparte).
    Devuelve el texto del motivo si debe rechazarse, o None si puede continuar.
    """
    if actividad.estado != Actividad.Estado.PUBLICADA:
        return "Esta actividad no acepta inscripciones."

    if actividad.organizador_id == participante.pk:
        return "No puedes inscribirte en tu propia actividad."


    if esta_inscrito(participante, actividad):
        return "Ya estás inscrito en esta actividad."

    conflicto = conflicto_de_horario(participante, actividad)

    if conflicto:
        otra = conflicto.actividad
        return (
            "No puedes inscribirte: el horario choca con tu inscripción en "
            f"«{otra.nombre}» ({_formato(otra.fecha_inicio)} a "
            f"{_formato(otra.fecha_fin)})."
        )

    return None