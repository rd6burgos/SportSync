from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from actividades.models import Actividad
from inscripciones.models import Inscripcion, Pago

from .models import Equipo, Partido, PartidoEquipo


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


def guardar_equipo(torneo_id, organizador, nombre, integrantes, equipo_id=None):
    """Crea un equipo o actualiza su nombre e integrantes."""
    nombre = nombre.strip()
    integrante_ids = {integrante.pk for integrante in integrantes}
    if not nombre:
        raise ValidationError("Escribe un nombre para el equipo.")
    if not integrante_ids:
        raise ValidationError("Selecciona al menos un integrante para el equipo.")

    with transaction.atomic():
        torneo = _bloquear_torneo(torneo_id, organizador)
        if torneo.estado not in ESTADOS_PARA_PROGRAMAR:
            raise ValidationError(
                "Solo se pueden gestionar equipos cuando las inscripciones "
                "están cerradas o el torneo está en curso."
            )

        equipo = None
        if equipo_id is not None:
            equipo = Equipo.objects.select_for_update().filter(
                pk=equipo_id, torneo=torneo
            ).first()
            if equipo is None:
                raise ValidationError("El equipo no pertenece a este torneo.")

        if Equipo.objects.filter(torneo=torneo, nombre__iexact=nombre).exclude(
            pk=getattr(equipo, "pk", None)
        ).exists():
            raise ValidationError("Ya existe un equipo con ese nombre en el torneo.")

        ids_validos = set(
            participantes_validos(torneo).values_list("pk", flat=True)
        )
        if not integrante_ids.issubset(ids_validos):
            raise ValidationError(
                "Todos los integrantes deben tener inscripción válida y, "
                "si aplica, el pago aprobado."
            )

        if equipo is not None and (
            equipo.partidos_como_a.filter(
                estado=PartidoEquipo.Estado.JUGADO
            ).exists()
            or equipo.partidos_como_b.filter(
                estado=PartidoEquipo.Estado.JUGADO
            ).exists()
        ) and set(equipo.integrantes.values_list("pk", flat=True)) != integrante_ids:
            raise ValidationError(
                "No se puede cambiar la plantilla de un equipo que ya tiene "
                "partidos jugados."
            )

        otros_equipos = Equipo.objects.filter(torneo=torneo).exclude(
            pk=getattr(equipo, "pk", None)
        )
        if otros_equipos.filter(integrantes__pk__in=integrante_ids).exists():
            raise ValidationError(
                "Cada participante solo puede pertenecer a un equipo del torneo."
            )

        if equipo is None:
            equipo = Equipo.objects.create(torneo=torneo, nombre=nombre)
        else:
            equipo.nombre = nombre
            equipo.save(update_fields=["nombre"])

        equipo.integrantes.set(integrante_ids)
        return equipo


def _exigir_equipo_valido(torneo, equipo):
    ids_validos = inscripciones_validas(torneo).values("participante_id")
    if not equipo.integrantes.filter(pk__in=ids_validos).exists():
        raise ValidationError(
            f"El equipo {equipo.nombre} debe tener al menos un integrante "
            "con inscripción válida."
        )


def crear_partido_equipo(
    torneo_id, organizador, equipo_a, equipo_b, fecha_hora, ronda=""
):
    """Programa un partido entre dos equipos del torneo."""
    with transaction.atomic():
        torneo = _bloquear_torneo(torneo_id, organizador)
        if torneo.estado not in ESTADOS_PARA_PROGRAMAR:
            raise ValidationError(
                "Solo se pueden programar partidos cuando las inscripciones "
                "están cerradas o el torneo está en curso."
            )
        if equipo_a.pk == equipo_b.pk:
            raise ValidationError("Un equipo no puede jugar contra sí mismo.")

        equipos = {
            equipo.pk: equipo
            for equipo in Equipo.objects.select_for_update().filter(
                torneo=torneo, pk__in=(equipo_a.pk, equipo_b.pk)
            )
        }
        if len(equipos) != 2:
            raise ValidationError("Ambos equipos deben pertenecer a este torneo.")
        equipo_a = equipos[equipo_a.pk]
        equipo_b = equipos[equipo_b.pk]
        _exigir_equipo_valido(torneo, equipo_a)
        _exigir_equipo_valido(torneo, equipo_b)

        if not torneo.fecha_inicio <= fecha_hora <= torneo.fecha_fin:
            raise ValidationError(
                "El partido debe programarse dentro del horario del torneo "
                f"({_formato(torneo.fecha_inicio)} a {_formato(torneo.fecha_fin)})."
            )

        return PartidoEquipo.objects.create(
            torneo=torneo,
            equipo_a=equipo_a,
            equipo_b=equipo_b,
            fecha_hora=fecha_hora,
            ronda=ronda.strip(),
        )


def registrar_resultado_equipo(partido_id, marcador_a, marcador_b, usuario):
    """Registra o corrige el resultado de un partido entre equipos."""
    with transaction.atomic():
        torneo_id = PartidoEquipo.objects.values_list(
            "torneo_id", flat=True
        ).get(pk=partido_id)
        torneo = _bloquear_torneo(torneo_id, usuario)
        partido = (
            PartidoEquipo.objects.select_for_update()
            .select_related("equipo_a", "equipo_b")
            .get(pk=partido_id)
        )

        if torneo.estado != Actividad.Estado.EN_CURSO:
            raise ValidationError(
                "Los resultados solo se registran mientras el torneo está en curso."
            )
        if partido.estado == PartidoEquipo.Estado.CANCELADO:
            raise ValidationError("Un partido cancelado no admite resultado.")

        for marcador in (marcador_a, marcador_b):
            if isinstance(marcador, bool) or not isinstance(marcador, int):
                raise ValidationError("Los marcadores deben ser números enteros.")
            if not 0 <= marcador <= MARCADOR_MAXIMO:
                raise ValidationError(
                    f"Cada marcador debe estar entre 0 y {MARCADOR_MAXIMO}."
                )

        _exigir_equipo_valido(torneo, partido.equipo_a)
        _exigir_equipo_valido(torneo, partido.equipo_b)

        partido.marcador_a = marcador_a
        partido.marcador_b = marcador_b
        partido.estado = PartidoEquipo.Estado.JUGADO
        partido.resultado_registrado_por = usuario
        partido.fecha_resultado = timezone.now()
        partido.save()
        return partido


def cancelar_partido_equipo(partido_id, usuario):
    """Cancela un partido entre equipos que todavía no se ha jugado."""
    with transaction.atomic():
        torneo_id = PartidoEquipo.objects.values_list(
            "torneo_id", flat=True
        ).get(pk=partido_id)
        torneo = _bloquear_torneo(torneo_id, usuario)
        partido = PartidoEquipo.objects.select_for_update().get(pk=partido_id)

        if torneo.estado not in ESTADOS_PARA_PROGRAMAR:
            raise ValidationError(
                "Ya no se pueden cancelar partidos: el torneo no está en curso "
                "ni con inscripciones cerradas."
            )
        if partido.estado != PartidoEquipo.Estado.PROGRAMADO:
            raise ValidationError(
                "Solo se pueden cancelar partidos entre equipos que todavía "
                "no se han jugado."
            )

        partido.estado = PartidoEquipo.Estado.CANCELADO
        partido.save(update_fields=["estado"])
        return partido


def tabla_posiciones_equipos(torneo):
    """Calcula la tabla ordenada por victorias, diferencia y goles a favor."""
    equipos = list(Equipo.objects.filter(torneo=torneo).order_by("nombre", "pk"))
    filas = {
        equipo.pk: {
            "equipo": equipo,
            "jugados": 0,
            "ganados": 0,
            "empatados": 0,
            "perdidos": 0,
            "goles_favor": 0,
            "goles_contra": 0,
            "diferencia_goles": 0,
        }
        for equipo in equipos
    }

    partidos = PartidoEquipo.objects.filter(
        torneo=torneo,
        estado=PartidoEquipo.Estado.JUGADO,
    ).select_related("equipo_a", "equipo_b")
    for partido in partidos:
        fila_a = filas[partido.equipo_a_id]
        fila_b = filas[partido.equipo_b_id]
        fila_a["jugados"] += 1
        fila_b["jugados"] += 1
        fila_a["goles_favor"] += partido.marcador_a
        fila_a["goles_contra"] += partido.marcador_b
        fila_b["goles_favor"] += partido.marcador_b
        fila_b["goles_contra"] += partido.marcador_a

        if partido.marcador_a > partido.marcador_b:
            fila_a["ganados"] += 1
            fila_b["perdidos"] += 1
        elif partido.marcador_a < partido.marcador_b:
            fila_b["ganados"] += 1
            fila_a["perdidos"] += 1
        else:
            fila_a["empatados"] += 1
            fila_b["empatados"] += 1

    resultado = list(filas.values())
    for fila in resultado:
        fila["diferencia_goles"] = fila["goles_favor"] - fila["goles_contra"]

    return sorted(
        resultado,
        key=lambda fila: (
            -fila["ganados"],
            -fila["diferencia_goles"],
            -fila["goles_favor"],
            fila["equipo"].nombre.casefold(),
            fila["equipo"].pk,
        ),
    )