import logging

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from actividades.models import Actividad

from .models import Inscripcion, Notificacion

logger = logging.getLogger(__name__)


def _fecha(fecha):
    return timezone.localtime(fecha).strftime("%d/%m/%Y %H:%M")


def _datos_actividad(actividad):
    return (
        f"Actividad: {actividad.nombre}\n"
        f"Lugar: {actividad.ubicacion}\n"
        f"Inicio: {_fecha(actividad.fecha_inicio)}\n"
        f"Fin: {_fecha(actividad.fecha_fin)}"
    )


# tipo -> (asunto, texto principal). El saludo y los datos se agregan después.
TEXTOS = {
    Notificacion.Tipo.INSCRIPCION_CONFIRMADA: (
        "Inscripción confirmada: {actividad}",
        "Tu inscripción quedó confirmada. Inicia sesión en SportSync para "
        "ver tu código QR de asistencia.",

    ),
    Notificacion.Tipo.LISTA_ESPERA: (
        "Estás en la lista de espera: {actividad}",
        "La actividad no tiene cupos disponibles, así que quedaste en la "
        "lista de espera. Si se libera un cupo, te avisaremos por este medio.",
    ),
    Notificacion.Tipo.PROMOCION: (
        "¡Se liberó un cupo! Ya estás inscrito en {actividad}",
        "Se liberó un cupo y tu inscripción pasó de la lista de espera a "
        "confirmada. Inicia sesión en SportSync para ver tu código QR.",
    ),
    Notificacion.Tipo.ACTIVIDAD_EN_CURSO: (
        "La actividad {actividad} ha comenzado",
        "El organizador inició la actividad en la que estás inscrito.",
    ),
    Notificacion.Tipo.ACTIVIDAD_FINALIZADA: (
        "La actividad {actividad} ha finalizado",
        "El organizador dio por finalizada la actividad en la que estabas "
        "inscrito. ¡Gracias por participar!",
    ),
    Notificacion.Tipo.ACTIVIDAD_CANCELADA: (
        "Actividad cancelada: {actividad}",
        "Lamentamos informarte que el organizador canceló la actividad en "
        "la que estabas inscrito.",
    ),
}

# Cambios de estado de la actividad que se avisan a los inscritos.
TIPO_POR_ESTADO = {
    Actividad.Estado.EN_CURSO: Notificacion.Tipo.ACTIVIDAD_EN_CURSO,
    Actividad.Estado.FINALIZADA: Notificacion.Tipo.ACTIVIDAD_FINALIZADA,
    Actividad.Estado.CANCELADA: Notificacion.Tipo.ACTIVIDAD_CANCELADA,

}


def enviar_notificacion(notificacion_id):
    """
    Envía una notificación ya registrada y guarda el resultado.

    Nunca lanza error: un correo que falla no debe romper la inscripción ni
    el cambio de estado que lo originó. El fallo queda registrado en la
    notificación (estado "fallida" y el motivo) para poder revisarlo.
    """
    notificacion = Notificacion.objects.get(pk=notificacion_id)

    if notificacion.estado == Notificacion.Estado.ENVIADA:
        return notificacion

    try:
        send_mail(
            notificacion.asunto,
            notificacion.mensaje,
            None,  # usa DEFAULT_FROM_EMAIL
            [notificacion.correo],
            fail_silently=False,
        )
    except Exception as error:
        notificacion.estado = Notificacion.Estado.FALLIDA
        notificacion.error = f"{type(error).__name__}: {error}"[:1000]
        notificacion.fecha_envio = None
        logger.warning("No se pudo enviar la notificación %s: %s", notificacion.pk, error)
    else:
        notificacion.estado = Notificacion.Estado.ENVIADA
        notificacion.error = ""

        notificacion.fecha_envio = timezone.now()

    notificacion.save(update_fields=["estado", "error", "fecha_envio"])
    return notificacion


def registrar_notificacion(destinatario, actividad, tipo):
    """
    Guarda la notificación y programa su envío para DESPUÉS de que la
    transacción actual termine bien. Si la operación que la originó se
    deshace, no se envía ningún correo.
    """
    asunto, texto = TEXTOS[tipo]

    notificacion = Notificacion.objects.create(
        destinatario=destinatario,
        actividad=actividad,
        correo=destinatario.email,
        tipo=tipo,
        asunto=asunto.format(actividad=actividad.nombre),
        mensaje=(
            f"Hola {destinatario.nombre_publico()},\n\n"
            f"{texto}\n\n"
            f"{_datos_actividad(actividad)}\n\n"
            "— Equipo SportSync"
        ),
    )

    transaction.on_commit(lambda: enviar_notificacion(notificacion.pk))
    return notificacion



# --- Eventos del sistema ---------------------------------------------------

def notificar_inscripcion(inscripcion):
    """Avisa al participante si quedó confirmado o en lista de espera."""
    if inscripcion.estado == Inscripcion.Estado.LISTA_ESPERA:
        tipo = Notificacion.Tipo.LISTA_ESPERA
    else:
        tipo = Notificacion.Tipo.INSCRIPCION_CONFIRMADA

    return registrar_notificacion(inscripcion.participante, inscripcion.actividad, tipo)


def notificar_promocion(inscripcion):
    """Avisa al participante que pasó de la lista de espera a confirmado."""
    return registrar_notificacion(
        inscripcion.participante,
        inscripcion.actividad,
        Notificacion.Tipo.PROMOCION,
    )


def notificar_cambio_estado(actividad):
    """
    Avisa a los inscritos (confirmados y en lista de espera) cuando la
    actividad pasa a En curso, Finalizada o Cancelada. Con otros estados no
    hace nada. Devuelve cuántos correos se registraron.
    """
    tipo = TIPO_POR_ESTADO.get(actividad.estado)

    if tipo is None:
        return 0


    inscripciones = (
        actividad.inscripciones.exclude(estado=Inscripcion.Estado.CANCELADA)
        .filter(participante__is_active=True)
        .exclude(participante__email="")
        .select_related("participante")
    )

    with transaction.atomic():
        for inscripcion in inscripciones:
            registrar_notificacion(inscripcion.participante, actividad, tipo)

    return len(inscripciones)