from django.urls import path

from . import views, vistas_publicas


app_name = "actividades"

urlpatterns = [
    path( "mi-panel/", views.panel_actividades_organizador,name="panel_actividades_organizador",),
    path("crear/",views.crear_actividad, name="crear_actividad",),
    path(
 "<int:actividad_id>/editar/", views.editar_actividad, name="editar_actividad",),
    path("<int:actividad_id>/cambiar-estado/", views.cambiar_estado_actividad,name="cambiar_estado_actividad",),
    path(
  "calendario/", vistas_publicas.calendario_publico,name="calendario_publico", ),
    path( "<int:actividad_id>/detalle/",vistas_publicas.detalle_publico,name="detalle_publico",),
]