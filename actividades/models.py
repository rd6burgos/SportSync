from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Actividad(models.Model):
    
    # Definición de estados posibles (CR-19)
    class Estado(models.TextChoices):
        BORRADOR = 'borrador', 'Borrador'
        PUBLICADA = 'publicada', 'Publicada'
        INSCRIPCION_CERRADA = 'inscripcion_cerrada', 'Inscripción Cerrada'
        EN_CURSO = 'en_curso', 'En Curso'
        FINALIZADA = 'finalizada', 'Finalizada'
        CANCELADA = 'cancelada', 'Cancelada'

    # Campos básicos de la actividad
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la actividad")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    deporte = models.CharField(max_length=100)
    fecha = models.DateField(verbose_name="Fecha del evento")
    hora = models.TimeField(verbose_name="Hora de inicio")
    lugar = models.CharField(max_length=200, verbose_name="Lugar o dirección")
    
    # Control de cupo (Punto 7 de Fase 5)
    cupo_maximo = models.PositiveIntegerField(
        verbose_name="Cupo máximo",
        help_text="Número máximo de participantes permitidos."
    )
    
    costo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Costo de inscripción"
    )
    
    # Estado actual (CR-19)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        verbose_name="Estado actual"
    )
    
    # Relación con el usuario organizador
    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='actividades_organizadas',
        limit_choices_to={'rol': 'organizador'}, # Solo muestra usuarios con rol organizador
        verbose_name="Organizador"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.fecha}"

    def clean(self):
        # Validación de regla de negocio: El cupo no puede ser cero o negativo
        if self.cupo_maximo <= 0:
            raise ValidationError("El cupo máximo debe ser un número mayor a cero.")
        super().clean()

    class Meta:
        verbose_name = "Actividad"
        verbose_name_plural = "Actividades"
        ordering = ['fecha', 'hora']