from django import forms

from .models import Actividad


class ActividadForm(forms.ModelForm):
    class Meta:
        model = Actividad
        fields = (
            "nombre",
            "descripcion",
            "tipo",
            "deporte",
            "ubicacion",
            "fecha_inicio",
            "fecha_fin",
            "cupo_maximo",
            "costo",
        )

        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "fecha_inicio": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "fecha_fin": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "cupo_maximo": forms.NumberInput(attrs={"min": 1}),
            "costo": forms.NumberInput(
                attrs={"min": 0, "step": "0.01"},
            ),
        }

        help_texts = {
            "costo": "Escribe 0 si la actividad es gratuita.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for nombre in ("fecha_inicio", "fecha_fin"):
            self.fields[nombre].input_formats = [
                "%Y-%m-%dT%H:%M",
            ]

        for field in self.fields.values():
            field.widget.attrs.update({
                "class": (
                    "w-full rounded-lg border border-slate-300 "
                    "bg-white px-4 py-3 text-slate-900 "
                    "focus:outline-none focus:ring-2 focus:ring-blue-600"
                ),
            })