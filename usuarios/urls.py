from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "usuarios"

urlpatterns = [
    path("registro/", views.registro, name="registro"),
    path("registro-exitoso/", views.registro_exitoso, name="registro_exitoso"),
    path("login/", auth_views.LoginView.as_view(template_name="usuarios/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path( "panel-organizador/", views.panel_organizador, name="panel_organizador", ),
    path( "panel-administrador/", views.panel_administrador, name="panel_administrador",),
    path("panel-participante/",views.panel_participante, name="panel_participante",),
    path( "solicitudes/<int:solicitud_id>/aprobar/", views.aprobar_solicitud,name="aprobar_solicitud",),
    path("solicitudes/<int:solicitud_id>/rechazar/",views.rechazar_solicitud, name="rechazar_solicitud",),
]