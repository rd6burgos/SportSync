from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario, SolicitudOrganizador


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "rol", "is_active", "is_staff")
    list_filter = ("rol", "is_active", "is_staff")
    search_fields = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name")}),
        ("Rol y permisos", {"fields": ("rol", "is_active", "is_staff", "is_superuser")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "rol", "password1", "password2"),
        }),
    )


@admin.register(SolicitudOrganizador)
class SolicitudOrganizadorAdmin(admin.ModelAdmin):
    list_display = ("participante", "estado", "fecha_solicitud", "revisado_por")
    list_filter = ("estado",)