from django import forms
from .models import Actividad
from django.utils import timezone

class ActividadForm(forms.ModelForm):
    """
    Formulario para crear/editar actividades.
    Ocultamos el estado porque siempre inicia como Borrador.
    """
    class Meta:
        model = Actividad
        # Campos que el usuario podrá editar
        fields = [
            'nombre', 'descripcion', 'deporte', 
            'fecha', 'hora', 'lugar', 
            'cupo_maximo', 'costo'
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'hora': forms.TimeInput(attrs={'type': 'time'}),
            'descripcion': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_fecha(self):
        """Valida que la fecha no sea anterior a hoy."""
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha < timezone.now().date():
            raise forms.ValidationError("No puedes crear actividades en el pasado.")
        return fecha

    def clean_cupo_maximo(self):
        """Valida que el cupo sea mayor a 0 (doble seguridad)."""
        cupo = self.cleaned_data.get('cupo_maximo')
        if cupo <= 0:
            raise forms.ValidationError("El cupo debe ser al menos 1.")
        return cupo