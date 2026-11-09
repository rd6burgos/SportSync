from django.contrib import admin

from .models import Partido


@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = (
        "torneo", "participante_a", "participante_b", "ronda",
        "fecha_hora", "estado", "marcador_a", "marcador_b",
    )
    list_filter = ("estado", "torneo")
    search_fields = (
        "participante_a__email", "participante_b__email", "torneo__nombre",
    )