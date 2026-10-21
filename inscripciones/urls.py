from django.urls import path

from . import views

app_name = "inscripciones"

urlpatterns = [
    path("pagos/", views.panel_pagos, name="panel_pagos"),
    path("pagos/<int:pago_id>/estado/", views.cambiar_estado_pago, name="cambiar_estado_pago"),
    path("<int:actividad_id>/inscribirse/", views.inscribirse, name="inscribirse"),
    path("<int:inscripcion_id>/", views.detalle_inscripcion, name="detalle"),
    path("<int:inscripcion_id>/cancelar/", views.cancelar_inscripcion, name="cancelar"),
    path("pagos/<int:pago_id>/paypal/crear/", views.paypal_crear_orden, name="paypal_crear_orden"),
    path("pagos/<int:pago_id>/paypal/capturar/", views.paypal_capturar_orden, name="paypal_capturar_orden"),
]