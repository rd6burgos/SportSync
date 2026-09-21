from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RegistroForm, SolicitudOrganizadorForm
from .decorators import roles_permitidos
from .models import Usuario, SolicitudOrganizador

# ==============================================================================
# VISTAS DE AUTENTICACIÓN (LOGIN / LOGOUT / REGISTRO)
# ==============================================================================

def registro(request):
    """Vista para registrar nuevos usuarios."""
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("usuarios:registro_exitoso")
    else:
        form = RegistroForm()
    return render(request, "usuarios/registro.html", {"form": form})

def registro_exitoso(request):
    """Muestra mensaje de éxito tras el registro."""
    return render(request, "usuarios/registro_exitoso.html")

def login_view(request):
    """Vista personalizada para iniciar sesión usando email."""
    if request.user.is_authenticated:
        return redirect('core:inicio')
        
    if request.method == 'POST':
        email = request.POST.get('username') # El input se llama 'username' pero es el email
        password = request.POST.get('password')
        next_url = request.POST.get('next', 'core:inicio')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect(next_url)
        else:
            # Si falla, mostramos el formulario con error
            return render(request, 'usuarios/login.html', {
                'form': {'errors': True}, 
                'next': next_url
            })
    
    # Si es GET, mostramos el formulario vacío
    next_url = request.GET.get('next', 'core:inicio')
    return render(request, 'usuarios/login.html', {'next': next_url})

def logout_view(request):
    """Cierra la sesión del usuario."""
    logout(request)
    return redirect('core:inicio')

# ==============================================================================
# VISTAS DE PANELES (ORGANIZADOR / ADMINISTRADOR / PARTICIPANTE)
# ==============================================================================

@roles_permitidos(Usuario.Rol.ORGANIZADOR, Usuario.Rol.ADMINISTRADOR)
def panel_organizador(request):
    """Área exclusiva para organizadores."""
    return HttpResponse("Acceso permitido: área de Organizador.")

@roles_permitidos(Usuario.Rol.ADMINISTRADOR)
def panel_administrador(request):
    """Panel para aprobar/rechazar solicitudes de organizador."""
    solicitudes = (
        SolicitudOrganizador.objects
        .filter(estado=SolicitudOrganizador.Estado.PENDIENTE)
        .select_related("participante")
        .order_by("fecha_solicitud")
    )
    return render(
        request,
        "usuarios/panel_administrador.html",
        {"solicitudes": solicitudes},
    )

@roles_permitidos(Usuario.Rol.PARTICIPANTE)
def panel_participante(request):
    """Panel para que el participante solicite ser organizador."""
    solicitudes = SolicitudOrganizador.objects.filter(participante=request.user)
    tiene_pendiente = solicitudes.filter(estado=SolicitudOrganizador.Estado.PENDIENTE).exists()
    form = SolicitudOrganizadorForm()

    if request.method == "POST":
        if tiene_pendiente:
            return redirect("usuarios:panel_participante")

        form = SolicitudOrganizadorForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.participante = request.user
            solicitud.estado = SolicitudOrganizador.Estado.PENDIENTE

            try:
                with transaction.atomic():
                    solicitud.save()
            except IntegrityError:
                if not solicitudes.filter(estado=SolicitudOrganizador.Estado.PENDIENTE).exists():
                    raise
            return redirect("usuarios:panel_participante")

    ultima_solicitud = solicitudes.order_by("-fecha_solicitud").first()
    return render(
        request,
        "usuarios/panel_participante.html",
        {
            "solicitud": ultima_solicitud,
            "form": form,
            "tiene_pendiente": tiene_pendiente,
        },
    )

# ==============================================================================
# VISTAS DE GESTIÓN DE SOLICITUDES (APROBAR / RECHAZAR)
# ==============================================================================

@roles_permitidos(Usuario.Rol.ADMINISTRADOR)
@require_POST
def aprobar_solicitud(request, solicitud_id):
    """Aprueba una solicitud y cambia el rol del usuario a ORGANIZADOR."""
    solicitud = get_object_or_404(SolicitudOrganizador, pk=solicitud_id)

    with transaction.atomic():
        actualizadas = SolicitudOrganizador.objects.filter(
            pk=solicitud.pk,
            estado=SolicitudOrganizador.Estado.PENDIENTE,
        ).update(
            estado=SolicitudOrganizador.Estado.APROBADA,
            revisado_por=request.user,
            fecha_revision=timezone.now(),
            comentario_revision="Tu solicitud fue aprobada.",
        )

        if actualizadas == 0:
            return redirect("usuarios:panel_administrador")

        usuarios_actualizados = Usuario.objects.filter(
            pk=solicitud.participante_id,
            rol=Usuario.Rol.PARTICIPANTE,
            is_active=True,
        ).update(
            rol=Usuario.Rol.ORGANIZADOR,
        )

        if usuarios_actualizados == 0:
            raise PermissionDenied("Solo se pueden aprobar solicitudes de participantes activos.")

    return redirect("usuarios:panel_administrador")

@roles_permitidos(Usuario.Rol.ADMINISTRADOR)
@require_POST
def rechazar_solicitud(request, solicitud_id):
    """Rechaza una solicitud de organizador."""
    solicitud = get_object_or_404(SolicitudOrganizador, pk=solicitud_id)

    SolicitudOrganizador.objects.filter(
        pk=solicitud.pk,
        estado=SolicitudOrganizador.Estado.PENDIENTE,
    ).update(
        estado=SolicitudOrganizador.Estado.RECHAZADA,
        revisado_por=request.user,
        fecha_revision=timezone.now(),
        comentario_revision="Tu solicitud fue rechazada.",
    )

    return redirect("usuarios:panel_administrador")