from django import forms

from .servicios import participantes_validos

CLASES = (
    "w-full rounded-lg border border-slate-300 bg-white px-4 py-3 "
    "text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
)


def _etiqueta(usuario):
    return f"{usuario.nombre_publico()} ({usuario.email})"


class PartidoForm(forms.Form):
    participante_a = forms.ModelChoiceField(
        label="Participante A", queryset=None, empty_label="Elige un participante"
    )
    participante_b = forms.ModelChoiceField(
        label="Participante B", queryset=None, empty_label="Elige un participante"
    )
    fecha_hora = forms.DateTimeField(
        label="Fecha y hora del partido",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    ronda = forms.CharField(
        label="Ronda o jornada (opcional)",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej.: Jornada 1, Semifinal"}),
    )


    def __init__(self, *args, torneo, **kwargs):
        super().__init__(*args, **kwargs)

        # Solo se pueden elegir participantes con inscripción válida.
        validos = participantes_validos(torneo)

        for nombre in ("participante_a", "participante_b"):
            self.fields[nombre].queryset = validos
            self.fields[nombre].label_from_instance = _etiqueta

        for campo in self.fields.values():
            campo.widget.attrs.update({"class": CLASES})