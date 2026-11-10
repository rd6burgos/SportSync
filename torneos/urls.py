from django.urls import path

from . import views

app_name = "torneos"

urlpatterns = [
    path("<int:actividad_id>/", views.partidos_publicos, name="partidos_publicos"),
    path("<int:actividad_id>/gestionar/", views.gestionar_partidos, name="gestionar_partidos"),
    path("<int:actividad_id>/gestionar/crear/", views.crear_partido_vista, name="crear_partido"),
    path("partidos/<int:partido_id>/resultado/", views.registrar_resultado_vista, name="registrar_resultado"),
    path("partidos/<int:partido_id>/cancelar/", views.cancelar_partido_vista, name="cancelar_partido"),
    path("<int:actividad_id>/equipos/guardar/", views.guardar_equipo_vista, name="guardar_equipo"),
    path("<int:actividad_id>/equipos/partidos/crear/", views.crear_partido_equipo_vista, name="crear_partido_equipo"),
    path("partidos-equipos/<int:partido_id>/resultado/", views.registrar_resultado_equipo_vista, name="registrar_resultado_equipo"),
    path("partidos-equipos/<int:partido_id>/cancelar/", views.cancelar_partido_equipo_vista, name="cancelar_partido_equipo"),
]