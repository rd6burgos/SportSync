from django.contrib import admin
from .models import Actividad

@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha', 'hora', 'deporte', 'estado', 'organizador')
    list_filter = ('estado', 'deporte', 'fecha')
    search_fields = ('nombre', 'descripcion')
    ordering = ('fecha', 'hora')