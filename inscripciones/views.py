import segno
from django.contrib.auth import get_user_model
from .validaciones import motivo_de_rechazo


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST, require_safe

from actividades.models import Actividad

from .models import Inscripcion


@login_required
@require_POST
@login_required
@require_POST

def inscribirse(request, actividad_id):
    inscripcion = None

    with transaction.atomic():
        # Se bloquea primero al participante y luego la actividad (siempre en
        # este orden). Así dos solicitudes simultáneas del mismo usuario no
        # pueden saltarse la validación de duplicados y horarios.
        participante = get_user_model().objects.select_for_update().get(
            pk=request.user.pk
        )
        actividad = get_object_or_404(
            Actividad.objects.select_for_update(),
            pk=actividad_id,
        )

        error = motivo_de_rechazo(participante, actividad)

        if error is None and actividad.cupos_disponibles() == 0:
            error = "No quedan cupos disponibles."

        if error is None:
            try:
                with transaction.atomic():
                    inscripcion = Inscripcion.objects.create(
                        participante=participante,
                        actividad=actividad,
                        estado=Inscripcion.Estado.CONFIRMADA,
                    )
            except IntegrityError:
                error = "Ya estás inscrito en esta actividad."

    if error:
        messages.error(request, error)
        return redirect("actividades:detalle_publico", actividad_id=actividad_id)

    return redirect("inscripciones:detalle", inscripcion_id=inscripcion.pk)


@login_required
@require_safe
def detalle_inscripcion(request, inscripcion_id):
    # Solo el dueño de la inscripción puede ver su QR.
    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related("actividad"),
        pk=inscripcion_id,
        participante=request.user,
    )

    qr_svg = None

    if inscripcion.estado == Inscripcion.Estado.CONFIRMADA:
        qr = segno.make(str(inscripcion.qr_token), error="m")
        qr_svg = mark_safe(
            qr.svg_inline(
                scale=1,
                border=2,
                dark="#000000",
                light="#ffffff",
                omitsize=True,
            )
        )

    return render(
        request,
        "inscripciones/detalle.html",
        {"inscripcion": inscripcion, "qr_svg": qr_svg},
    )


@login_required
@require_POST
def cancelar_inscripcion(request, inscripcion_id):
    with transaction.atomic():
        inscripcion = get_object_or_404(
            Inscripcion.objects.select_for_update().select_related("actividad"),
            pk=inscripcion_id,
            participante=request.user,
        )

        estados_permitidos = (
            Actividad.Estado.PUBLICADA,
            Actividad.Estado.INSCRIPCION_CERRADA,
        )

        if inscripcion.estado == Inscripcion.Estado.CANCELADA:
            messages.error(request, "Esta inscripción ya estaba cancelada.")
        elif inscripcion.actividad.estado not in estados_permitidos:
            messages.error(
                request,
                "Ya no puedes cancelar: la actividad está en curso, "
                "finalizó o fue cancelada.",
            )
        else:
            inscripcion.estado = Inscripcion.Estado.CANCELADA
            inscripcion.save(update_fields=["estado"])
            # Etapa 11: aquí se promoverá al primero de la lista de espera.
            messages.success(request, "Inscripción cancelada.")

    return redirect(
        "actividades:detalle_publico",
        actividad_id=inscripcion.actividad_id,
    )