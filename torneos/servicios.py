from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from actividades.models import Actividad
from inscripciones.models import Inscripcion, Pago

from .models import Partido


# Se programan partidos cuando la lista de participantes ya está definida.
ESTADOS_PARA_PROGRAMAR = (
    Actividad.Estado.INSCRIPCION_CERRADA,
    Actividad.Estado.EN_CURSO,
)

MARCADOR_MAXIMO = 999


# --- Participantes válidos ---------------------------------------------------

def inscripciones_validas(torneo):
    """
    Inscripciones que dan derecho a jugar: confirmadas y, si el torneo
    tiene costo, con el pago aprobado (la misma regla que habilita el QR).
    """
    return (
        Inscripcion.objects.filter(
            actividad=torneo,
            estado=Inscripcion.Estado.CONFIRMADA,

        )
        .filter(Q(pago__isnull=True) | Q(pago__estado=Pago.Estado.APROBADO))
        .select_related("participante")
    )


def participantes_validos(torneo):
    usuarios = get_user_model().objects.filter(
        pk__in=inscripciones_validas(torneo).values("participante_id")
    )

    return usuarios.order_by("first_name", "last_name", "email")


def es_participante_valido(torneo, usuario):
    return inscripciones_validas(torneo).filter(participante=usuario).exists()


# --- Reglas internas -----------------------------------------------------------

def _bloquear_torneo(torneo_id, organizador):
    """Bloquea el torneo y comprueba que lo maneje su organizador."""
    torneo = Actividad.objects.select_for_update().get(pk=torneo_id)

    if torneo.tipo != Actividad.Tipo.TORNEO:
        raise ValidationError("Esta actividad no es un torneo.")

    if torneo.organizador_id != organizador.pk:
        raise ValidationError("Solo el organizador del torneo puede gestionar sus partidos.")

    return torneo



def _formato(fecha):
    return timezone.localtime(fecha).strftime("%d/%m/%Y %H:%M")


def _exigir_participante_valido(torneo, usuario):
    if not es_participante_valido(torneo, usuario):
        raise ValidationError(
            f"{usuario.nombre_publico()} no tiene una inscripción válida en este "
            "torneo (debe estar confirmada y, si el torneo tiene costo, con el "
            "pago aprobado)."
        )





















# --- Operaciones -----------------------------------------------------------------

def crear_partido(torneo_id, organizador, participante_a, participante_b, fecha_hora, ronda=""):
    """
    Programa un partido. Debe existir el torneo y ambos participantes deben
    tener una inscripción válida. Lanza ValidationError con el motivo.
    """
    with transaction.atomic():
        torneo = _bloquear_torneo(torneo_id, organizador)

        if torneo.estado not in ESTADOS_PARA_PROGRAMAR:
            raise ValidationError(
                "Solo se pueden programar partidos cuando las inscripciones "
                "están cerradas o el torneo está en curso."
            )

        if participante_a.pk == participante_b.pk:
            raise ValidationError("Un participante no puede jugar contra sí mismo.")


        _exigir_participante_valido(torneo, participante_a)
        _exigir_participante_valido(torneo, participante_b)

        if not (torneo.fecha_inicio <= fecha_hora <= torneo.fecha_fin):
            raise ValidationError(
                "El partido debe programarse dentro del horario del torneo "
                f"({_formato(torneo.fecha_inicio)} a {_formato(torneo.fecha_fin)})."
            )

        return Partido.objects.create(
            torneo=torneo,
            participante_a=participante_a,
            participante_b=participante_b,
            fecha_hora=fecha_hora,
            ronda=ronda.strip(),
        )














def registrar_resultado(partido_id, marcador_a, marcador_b, usuario):
    """
    Registra (o corrige) el resultado de un partido mientras el torneo está
    en curso. Guarda quién lo hizo y cuándo. Lanza ValidationError si no
    se puede.
    """
    with transaction.atomic():
        torneo_id = Partido.objects.values_list("torneo_id", flat=True).get(pk=partido_id)
        torneo = _bloquear_torneo(torneo_id, usuario)
        partido = (
            Partido.objects.select_for_update()
            .select_related("participante_a", "participante_b")
            .get(pk=partido_id)

        )

        if torneo.estado != Actividad.Estado.EN_CURSO:
            raise ValidationError(
                "Los resultados solo se registran mientras el torneo está en curso."
            )

        if partido.estado == Partido.Estado.CANCELADO:
            raise ValidationError("Un partido cancelado no admite resultado.")

        for marcador in (marcador_a, marcador_b):
            if isinstance(marcador, bool) or not isinstance(marcador, int):
                raise ValidationError("Los marcadores deben ser números enteros.")

            if not 0 <= marcador <= MARCADOR_MAXIMO:
                raise ValidationError(
                    f"Cada marcador debe estar entre 0 y {MARCADOR_MAXIMO}."
                )

        # Si alguien canceló su inscripción después de programar el partido,
        # su resultado ya no es válido.
        _exigir_participante_valido(torneo, partido.participante_a)
        _exigir_participante_valido(torneo, partido.participante_b)

        partido.marcador_a = marcador_a
        partido.marcador_b = marcador_b
        partido.estado = Partido.Estado.JUGADO
        partido.resultado_registrado_por = usuario
        partido.fecha_resultado = timezone.now()
        partido.save()

        return partido



















def cancelar_partido(partido_id, usuario):
    """Cancela un partido que todavía no se ha jugado."""
    with transaction.atomic():
        torneo_id = Partido.objects.values_list("torneo_id", flat=True).get(pk=partido_id)
        torneo = _bloquear_torneo(torneo_id, usuario)
        partido = Partido.objects.select_for_update().get(pk=partido_id)

        if torneo.estado not in ESTADOS_PARA_PROGRAMAR:
            raise ValidationError(
                "Ya no se pueden cancelar partidos: el torneo no está en curso "
                "ni con inscripciones cerradas."
            )

        if partido.estado != Partido.Estado.PROGRAMADO:
            raise ValidationError(
                "Solo se pueden cancelar partidos que no se han jugado. Para un "
                "partido jugado, corrige el resultado."
            )

        partido.estado = Partido.Estado.CANCELADO
        partido.save(update_fields=["estado"])

        return partido