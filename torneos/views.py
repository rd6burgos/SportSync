from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from actividades.models import Actividad
from usuarios.decorators import roles_permitidos
from usuarios.models import Usuario

from .forms import PartidoForm
from .models import Partido
from .servicios import (
    ESTADOS_PARA_PROGRAMAR,
    cancelar_partido,
    crear_partido,
    participantes_validos,
    registrar_resultado,
)


def _torneo_del_organizador(request, actividad_id):
    return get_object_or_404(
        Actividad,
        pk=actividad_id,
        organizador=request.user,
        tipo=Actividad.Tipo.TORNEO,
    )


def _pagina_de_gestion(request, torneo, form):
    validos = participantes_validos(torneo)
    ids_validos = set(validos.values_list("pk", flat=True))

    partidos = list(
        torneo.partidos.select_related(
            "participante_a", "participante_b", "resultado_registrado_por"
        )
    )

    for partido in partidos:
        # Un participante pudo cancelar su inscripción después de programarlo.
        partido.valido = (
            partido.participante_a_id in ids_validos
            and partido.participante_b_id in ids_validos
        )

    return render(
        request,
        "torneos/gestionar_partidos.html",
        {
            "torneo": torneo,
            "form": form,
            "partidos": partidos,
            "total_validos": len(ids_validos),
            "puede_programar": torneo.estado in ESTADOS_PARA_PROGRAMAR,
            "puede_registrar": torneo.estado == Actividad.Estado.EN_CURSO,
        },
    )


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_safe
def gestionar_partidos(request, actividad_id):
    torneo = _torneo_del_organizador(request, actividad_id)

    return _pagina_de_gestion(request, torneo, PartidoForm(torneo=torneo))


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_POST
def crear_partido_vista(request, actividad_id):
    torneo = _torneo_del_organizador(request, actividad_id)
    form = PartidoForm(request.POST, torneo=torneo)

    if form.is_valid():
        try:
            crear_partido(
                torneo.pk,
                request.user,
                form.cleaned_data["participante_a"],
                form.cleaned_data["participante_b"],
                form.cleaned_data["fecha_hora"],
                form.cleaned_data["ronda"],
            )
        except ValidationError as error:
            for mensaje in error.messages:
                form.add_error(None, mensaje)
        else:
            messages.success(request, "Partido programado.")
            return redirect("torneos:gestionar_partidos", actividad_id=torneo.pk)

    return _pagina_de_gestion(request, torneo, form)


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_POST
def registrar_resultado_vista(request, partido_id):
    partido = get_object_or_404(
        Partido, pk=partido_id, torneo__organizador=request.user
    )

    try:
        marcador_a = int(request.POST.get("marcador_a", ""))
        marcador_b = int(request.POST.get("marcador_b", ""))
    except ValueError:
        messages.error(request, "Escribe un marcador numérico para cada participante.")
    else:
        try:
            registrar_resultado(partido.pk, marcador_a, marcador_b, request.user)
        except ValidationError as error:
            for mensaje in error.messages:
                messages.error(request, mensaje)
        else:
            messages.success(request, "Resultado guardado.")

    return redirect("torneos:gestionar_partidos", actividad_id=partido.torneo_id)


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_POST
def cancelar_partido_vista(request, partido_id):
    partido = get_object_or_404(
        Partido, pk=partido_id, torneo__organizador=request.user
    )

    try:
        cancelar_partido(partido.pk, request.user)
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
    else:
        messages.success(request, "Partido cancelado.")

    return redirect("torneos:gestionar_partidos", actividad_id=partido.torneo_id)


@require_safe
def partidos_publicos(request, actividad_id):
    """Partidos y resultados de un torneo, visibles para todos."""
    torneo = get_object_or_404(Actividad, pk=actividad_id, tipo=Actividad.Tipo.TORNEO)

    if torneo.estado == Actividad.Estado.BORRADOR:
        # Un borrador todavía no es público.
        return redirect("actividades:catalogo")

    partidos = torneo.partidos.select_related("participante_a", "participante_b")

    return render(
        request,
        "torneos/partidos_publicos.html",
        {"torneo": torneo, "partidos": partidos},
    )