from django.contrib import admin

from .models import Equipo, Partido, PartidoEquipo


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


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "torneo")
    list_filter = ("torneo",)
    search_fields = ("nombre", "torneo__nombre", "integrantes__email")


@admin.register(PartidoEquipo)
class PartidoEquipoAdmin(admin.ModelAdmin):
    list_display = (
        "torneo", "equipo_a", "equipo_b", "ronda",
        "fecha_hora", "estado", "marcador_a", "marcador_b",
    )
    list_filter = ("estado", "torneo")
    search_fields = ("equipo_a__nombre", "equipo_b__nombre", "torneo__nombre")