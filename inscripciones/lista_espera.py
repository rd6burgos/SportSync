from actividades.models import Actividad

from .models import Inscripcion


# Estados de la actividad en los que un cupo liberado se vuelve a ocupar.
ESTADOS_QUE_PROMUEVEN = (
    Actividad.Estado.PUBLICADA,
    Actividad.Estado.INSCRIPCION_CERRADA,
)


def hay_lista_espera(actividad):
    """True si hay al menos una inscripción esperando cupo en la actividad."""
    return actividad.inscripciones.filter(
        estado=Inscripcion.Estado.LISTA_ESPERA
    ).exists()


def promover_lista_espera(actividad):
    """
    Ocupa los cupos libres de la actividad con los primeros de la lista de
    espera (por orden de inscripción) y devuelve las inscripciones promovidas.

    Es "elegible" quien sigue en lista de espera y tiene la cuenta activa.

    IMPORTANTE: llamarla dentro de transaction.atomic() y con la actividad ya
    bloqueada con select_for_update(), para que el conteo de cupos sea fiable.
    Es segura de repetir: si no hay cupos libres o nadie espera, no hace nada.
    """
    if actividad.estado not in ESTADOS_QUE_PROMUEVEN:
        return []


    libres = actividad.cupos_disponibles()

    if libres <= 0:
        return []

    candidatas = list(
        actividad.inscripciones.filter(
            estado=Inscripcion.Estado.LISTA_ESPERA,
            participante__is_active=True,
        )
        .select_related("participante")
        .order_by("fecha_inscripcion", "pk")[:libres]
    )

    for inscripcion in candidatas:
        inscripcion.estado = Inscripcion.Estado.CONFIRMADA
        inscripcion.save(update_fields=["estado"])

    return candidatas