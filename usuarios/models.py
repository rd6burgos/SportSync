from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from django.conf import settings

# MODELO DE USUARIO PERSONALIZADO 
# Se crea un modelo de usuario personalizado para utilizar el correo electrónico como identificador único en lugar del nombre de usuario.
class UsuarioManager(BaseUserManager):

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email.strip())

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")

        email = self.normalize_email(email.strip()).lower()
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)

        return usuario

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("rol", self.model.Rol.ADMINISTRADOR)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El administrador debe tener is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El administrador debe tener is_superuser=True.")

        if extra_fields.get("rol") != self.model.Rol.ADMINISTRADOR:
            raise ValueError("El superusuario debe tener rol Administrador.")

        return self.create_user(email, password, **extra_fields)







    




class Usuario(AbstractUser):

    class Rol(models.TextChoices):
        PARTICIPANTE = "participante", "Participante"
        ORGANIZADOR = "organizador", "Organizador"
        ADMINISTRADOR = "administrador", "Administrador"

    rol = models.CharField(
        "rol",
        max_length=20,
        choices=Rol.choices,
        default=Rol.PARTICIPANTE,
    )

    username = None
    email = models.EmailField("correo electrónico", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def nombre_publico(self):
        # Nombre para mostrar a otros usuarios, sin exponer el correo completo.
        return self.get_full_name().strip() or self.email.split("@")[0]

    def __str__(self):
        return self.email











class SolicitudOrganizador(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"

    participante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitudes_organizador",
    )

    motivo = models.TextField(
        "motivo de la solicitud",
        max_length=1000,
    )

    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )

    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
    )

    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_revisadas",
    )

    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
    )

    comentario_revision = models.TextField(
        max_length=1000,
        blank=True,
    )











    class Meta:
        ordering = ["-fecha_solicitud"]
        constraints = [
            models.UniqueConstraint(
                fields=["participante"],
                condition=models.Q(estado="pendiente"),
                name="una_solicitud_pendiente_por_usuario",
            ),
        ]

    
    

    def __str__(self):
        return (
            f"{self.participante.email} - "
            f"{self.get_estado_display()}"
        )