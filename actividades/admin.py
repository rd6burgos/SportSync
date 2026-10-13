from django.contrib import admin

from .models import Actividad


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizador", "estado", "fecha_inicio", "cupo_maximo")
    list_filter = ("estado", "tipo")
    search_fields = ("nombre", "deporte")