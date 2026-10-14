from django.contrib import admin

from .models import Inscripcion


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("participante", "actividad", "estado", "fecha_inscripcion")
    list_filter = ("estado",)
    readonly_fields = ("qr_token", "fecha_inscripcion")