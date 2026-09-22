from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from usuarios.decorators import roles_permitidos
from usuarios.models import Usuario

from .forms import ActividadForm
from .models import Actividad


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
def panel_actividades_organizador(request):
    actividades = Actividad.objects.filter(
        organizador=request.user,
    )

    return render(
        request,
        "actividades/panel_actividades_organizador.html",
        {"actividades": actividades},
    )


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_http_methods(["GET", "POST"])
def crear_actividad(request):
    if request.method == "POST":
        form = ActividadForm(request.POST)

        if form.is_valid():
            actividad = form.save(commit=False)
            actividad.organizador = request.user
            actividad.estado = Actividad.Estado.BORRADOR
            actividad.save()

            messages.success(
                request,
                "Actividad creada como borrador.",
            )

            return redirect(
                "actividades:panel_actividades_organizador"
            )

    else:
        form = ActividadForm()

    return render(
        request,
        "actividades/formulario_actividad.html",
        {"form": form},
    )


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_http_methods(["GET", "POST"])
def editar_actividad(request, actividad_id):
    actividad = get_object_or_404(
        Actividad,
        pk=actividad_id,
        organizador=request.user,
        estado=Actividad.Estado.BORRADOR,
    )

    if request.method == "POST":
        form = ActividadForm(
            request.POST,
            instance=actividad,
        )

        if form.is_valid():
            campos_editables = (
                "nombre",
                "descripcion",
                "tipo",
                "deporte",
                "ubicacion",
                "fecha_inicio",
                "fecha_fin",
                "cupo_maximo",
                "costo",
            )

            datos = {
                campo: form.cleaned_data[campo]
                for campo in campos_editables
            }

            actualizadas = Actividad.objects.filter(
                pk=actividad.pk,
                organizador=request.user,
                estado=Actividad.Estado.BORRADOR,
            ).update(**datos)

            if actualizadas:
                messages.success(
                    request,
                    "Actividad actualizada correctamente.",
                )
            else:
                messages.error(
                    request,
                    "No se guardaron los cambios porque la actividad "
                    "ya no está en borrador.",
                )

            return redirect(
                "actividades:panel_actividades_organizador"
            )

    else:
        form = ActividadForm(instance=actividad)

    return render(
        request,
        "actividades/formulario_actividad.html",
        {
            "form": form,
            "actividad": actividad,
        },
    )


@roles_permitidos(Usuario.Rol.ORGANIZADOR)
@require_POST
def cambiar_estado_actividad(request, actividad_id):
    actividad = get_object_or_404(
        Actividad,
        pk=actividad_id,
        organizador=request.user,
    )

    nuevo_estado = request.POST.get("estado", "")

    try:
        actividad.cambiar_estado(nuevo_estado)

    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)

    else:
        messages.success(
            request,
            f"Estado actualizado a: {actividad.get_estado_display()}.",
        )

    return redirect(
        "actividades:panel_actividades_organizador"
    )