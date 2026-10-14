from django.urls import path

from . import views

app_name = "inscripciones"

urlpatterns = [
    path("<int:actividad_id>/inscribirse/", views.inscribirse, name="inscribirse"),
    path("<int:inscripcion_id>/", views.detalle_inscripcion, name="detalle"),
    path("<int:inscripcion_id>/cancelar/", views.cancelar_inscripcion, name="cancelar"),
]