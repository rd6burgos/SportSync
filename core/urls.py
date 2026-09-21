from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('acerca-de/', views.acerca, name='acerca_de'),  # <-- Cambia aquí
]