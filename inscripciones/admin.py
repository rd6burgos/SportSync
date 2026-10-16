from django.contrib import admin, messages

from .models import Inscripcion, Notificacion
from .notificaciones import enviar_notificacion


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("participante", "actividad", "estado", "fecha_inscripcion")
    list_filter = ("estado",)
    readonly_fields = ("qr_token", "fecha_inscripcion")


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("fecha_creacion", "correo", "tipo", "estado", "actividad")
    list_filter = ("estado", "tipo")
    search_fields = ("correo", "asunto")
    actions = ["reintentar_envio"]

    # Es un registro: se consulta, no se edita ni se crea a mano.
    readonly_fields = (
        "destinatario", "actividad", "correo", "tipo", "asunto", "mensaje",
        "estado", "error", "fecha_creacion", "fecha_envio",
    )

    def has_add_permission(self, request):
        return False

    @admin.action(description="Reintentar el envío de las seleccionadas (fallidas)")
    def reintentar_envio(self, request, queryset):
        fallidas = queryset.filter(estado=Notificacion.Estado.FALLIDA)

        enviadas = 0

        for notificacion in fallidas:
            if enviar_notificacion(notificacion.pk).estado == Notificacion.Estado.ENVIADA:
                enviadas += 1

        self.message_user(
            request,
            f"Se reenviaron {enviadas} de {fallidas.count()} notificaciones fallidas.",
            messages.SUCCESS if enviadas == fallidas.count() else messages.WARNING,
        )