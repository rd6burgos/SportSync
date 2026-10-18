import segno

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST, require_safe

from actividades.models import Actividad
from usuarios.decorators import roles_permitidos
from usuarios.models import Usuario

from .lista_espera import hay_lista_espera, promover_lista_espera
from .models import Inscripcion, Pago
from .notificaciones import notificar_inscripcion, notificar_promocion
from .pagos import cancelar_pago, crear_pago_si_corresponde, resolver_pago
from .validaciones import motivo_de_rechazo


from django.http import JsonResponse
from .models import Pago
from .pagos import resolver_pago
from .services_paypal import crear_orden_paypal, capturar_orden_paypal

from django.conf import settings
















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

        if error is None:
            # Entra confirmado solo si hay cupo Y nadie está esperando:
            # quien ya está en la lista de espera tiene prioridad.
            if actividad.cupos_disponibles() > 0 and not hay_lista_espera(actividad):
                estado = Inscripcion.Estado.CONFIRMADA
            else:
                estado = Inscripcion.Estado.LISTA_ESPERA

            try:
                with transaction.atomic():
                    inscripcion = Inscripcion.objects.create(
                        participante=participante,
                        actividad=actividad,
                        estado=estado,
                    )
                    # CR-12: si la actividad tiene costo, nace con pago pendiente.
                    crear_pago_si_corresponde(inscripcion)
            except IntegrityError:
                error = "Ya estás inscrito en esta actividad."
            else:
                # CR-13: avisa por correo si quedó confirmado o en espera.
                notificar_inscripcion(inscripcion)


    if error:
        messages.error(request, error)
        return redirect("actividades:detalle_publico", actividad_id=actividad_id)

    return redirect("inscripciones:detalle", inscripcion_id=inscripcion.pk)






























@login_required
@require_safe
def detalle_inscripcion(request, inscripcion_id):
    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related("actividad"),
        pk=inscripcion_id,
        participante=request.user,
    )

    qr_svg = None
    if inscripcion.qr_habilitado:
        qr = segno.make(str(inscripcion.qr_token), error="m")
        qr_svg = mark_safe(
            qr.svg_inline(scale=1, border=2, dark="#000000", light="#ffffff", omitsize=True)
        )

    return render(
        request,
        "inscripciones/detalle.html",
        {
            "inscripcion": inscripcion,
            "qr_svg": qr_svg,
            "pago": inscripcion.pago_actual,
            "paypal_client_id": settings.PAYPAL_CLIENT_ID,  # ← ESTA LÍNEA
        },
    )
































@login_required
@require_POST
def cancelar_inscripcion(request, inscripcion_id):
    # Primero se comprueba que la inscripción sea del usuario (sin bloquear).
    inscripcion = get_object_or_404(
        Inscripcion,
        pk=inscripcion_id,
        participante=request.user,
    )

    with transaction.atomic():
        # Se bloquea la actividad para que cancelar y promover sea una sola
        # operación frente a otras inscripciones o cancelaciones simultáneas.
        actividad = Actividad.objects.select_for_update().get(
            pk=inscripcion.actividad_id
        )
        # Se relee el estado actual, ya con la actividad bloqueada.
        inscripcion.refresh_from_db()

        estados_permitidos = (

            Actividad.Estado.PUBLICADA,
            Actividad.Estado.INSCRIPCION_CERRADA,
        )

        if inscripcion.estado == Inscripcion.Estado.CANCELADA:
            messages.error(request, "Esta inscripción ya estaba cancelada.")
        elif actividad.estado not in estados_permitidos:
            messages.error(
                request,
                "Ya no puedes cancelar: la actividad está en curso, "
                "finalizó o fue cancelada.",
            )
        else:
            inscripcion.estado = Inscripcion.Estado.CANCELADA
            inscripcion.save(update_fields=["estado"])

            # CR-12: el pago de una inscripción cancelada queda cancelado.
            cancelar_pago(inscripcion)

            # CR-04: si se liberó un cupo, entra el primero de la lista de
            # espera. Si quien canceló estaba en la lista, no hay cupo libre
            # y esta llamada no hace nada.
            for promovida in promover_lista_espera(actividad):
                # CR-13: avisa a quien entró desde la lista de espera.
                notificar_promocion(promovida)

            messages.success(request, "Inscripción cancelada.")

    return redirect(
        "actividades:detalle_publico",
        actividad_id=inscripcion.actividad_id,
    )



# --- Panel de pagos del organizador (CR-12) ---------------------------------

FILTROS_PAGOS = {
    "gestionar": "Por gestionar",
    "aprobado": "Aprobados",
    "rechazado": "Rechazados",
    "cancelado": "Cancelados",
    "todos": "Todos",
}































@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_safe
def panel_pagos(request):
    filtro = request.GET.get("filtro", "gestionar")

    if filtro not in FILTROS_PAGOS:
        filtro = "gestionar"

    # Solo los pagos de actividades de este organizador.
    pagos = Pago.objects.filter(
        inscripcion__actividad__organizador=request.user
    ).select_related("inscripcion__participante", "inscripcion__actividad")

    if filtro == "gestionar":
        # Los que esperan acción: pendientes o en revisión, con cupo confirmado.
        pagos = pagos.filter(
            estado__in=(Pago.Estado.PENDIENTE, Pago.Estado.EN_REVISION),
            inscripcion__estado=Inscripcion.Estado.CONFIRMADA,
        )

    elif filtro != "todos":
        pagos = pagos.filter(estado=filtro)

    pagos = pagos.order_by("inscripcion__actividad__fecha_inicio", "fecha_creacion")

    return render(
        request,
        "inscripciones/panel_pagos.html",
        {
            "pagos": pagos,
            "filtro": filtro,
            "filtros": FILTROS_PAGOS.items(),
        },
    )

























@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_POST
def cambiar_estado_pago(request, pago_id):
    # El pago debe ser de una actividad de este organizador.
    pago = get_object_or_404(
        Pago,
        pk=pago_id,
        inscripcion__actividad__organizador=request.user,
    )

    nuevo_estado = request.POST.get("estado", "")

    try:
        pago = resolver_pago(pago.pk, nuevo_estado, request.user)

    except ValidationError as error:

        for mensaje in error.messages:
            messages.error(request, mensaje)

    else:
        messages.success(
            request,
            f"Pago de {pago.inscripcion.participante.nombre_publico()} "
            f"actualizado a: {pago.get_estado_display()}.",
        )

    filtro = request.POST.get("filtro", "gestionar")

    if filtro not in FILTROS_PAGOS:
        filtro = "gestionar"

    return redirect(f"{reverse('inscripciones:panel_pagos')}?filtro={filtro}")



















@login_required
@require_POST
def paypal_crear_orden(request, pago_id):
    pago = get_object_or_404(
        Pago, pk=pago_id, inscripcion__participante=request.user
    )
    if pago.estado != Pago.Estado.PENDIENTE:
        return JsonResponse({"error": "El pago no está pendiente."}, status=400)

    try:
        order_id = crear_orden_paypal(pago)
        return JsonResponse({"id": order_id})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)








@login_required
@require_POST
def paypal_capturar_orden(request, pago_id):
    pago = get_object_or_404(
        Pago, pk=pago_id, inscripcion__participante=request.user
    )
    order_id = request.POST.get("order_id")

    try:
        capture_id = capturar_orden_paypal(order_id, pago)
        pago.paypal_capture_id = capture_id
        pago.metodo = Pago.Metodo.PAYPAL
        pago.save()

        # Transición del estado a En Revisión / Aprobado
        pago.estado = Pago.Estado.APROBADO
        pago.fecha_pago = timezone.now()
        pago.save()

        messages.success(request, "¡Pago completado exitosamente con PayPal!")
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)