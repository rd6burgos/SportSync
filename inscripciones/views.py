from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from actividades.models import Actividad

from .models import Inscripcion


@login_required
@require_POST
def inscribirse(request, actividad_id):
    with transaction.atomic():
        actividad = get_object_or_404(
            Actividad.objects.select_for_update(),
            pk=actividad_id,
        )

        error = None

        if actividad.estado != Actividad.Estado.PUBLICADA:
            error = "Esta actividad no acepta inscripciones."
        elif actividad.organizador == request.user:
            error = "No puedes inscribirte en tu propia actividad."
        elif Inscripcion.objects.filter(
            participante=request.user,
            actividad=actividad,
        ).exclude(estado=Inscripcion.Estado.CANCELADA).exists():
            error = "Ya estás inscrito en esta actividad."
        elif actividad.cupos_disponibles() == 0:

            error = "No quedan cupos disponibles."

        if error is None:
            try:
                with transaction.atomic():
                    Inscripcion.objects.create(
                        participante=request.user,
                        actividad=actividad,
                        estado=Inscripcion.Estado.CONFIRMADA,
                    )
            except IntegrityError:
                error = "Ya estás inscrito en esta actividad."

    if error:
        messages.error(request, error)
    else:
        messages.success(request, "Inscripción confirmada.")

    return redirect("actividades:detalle_publico", actividad_id=actividad_id)