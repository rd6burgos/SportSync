from django.urls import path

from . import views

app_name = "inscripciones"

urlpatterns = [
    path("<int:actividad_id>/inscribirse/", views.inscribirse, name="inscribirse"),
]