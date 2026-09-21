from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    path('registro-exitoso/', views.registro_exitoso, name='registro_exitoso'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('panel-participante/', views.panel_participante, name='panel_participante'),
    path('panel-organizador/', views.panel_organizador, name='panel_organizador'),
    path('panel-administrador/', views.panel_administrador, name='panel_administrador'),
    path('aprobar-solicitud/<int:solicitud_id>/', views.aprobar_solicitud, name='aprobar_solicitud'),
    path('rechazar-solicitud/<int:solicitud_id>/', views.rechazar_solicitud, name='rechazar_solicitud'),
]