from django import forms
from django.db.models import Q

from .models import Equipo
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


class EquipoForm(forms.Form):
    nombre = forms.CharField(label="Nombre del equipo", max_length=80)
    integrantes = forms.ModelMultipleChoiceField(
        label="Integrantes",
        queryset=None,
        required=True,
        widget=forms.SelectMultiple(attrs={"size": 6}),
        help_text="Mantén Ctrl (Windows) o Cmd (Mac) para elegir varios participantes.",
    )

    def __init__(self, *args, torneo, equipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        validos = participantes_validos(torneo)
        equipos = Equipo.objects.filter(torneo=torneo)
        if equipo is not None:
            equipos = equipos.exclude(pk=equipo.pk)

        asignados = equipos.values_list("integrantes__pk", flat=True).exclude(
            integrantes__pk__isnull=True
        )
        integrantes_actuales = (
            equipo.integrantes.values_list("pk", flat=True)
            if equipo is not None
            else ()
        )
        self.fields["integrantes"].queryset = validos.filter(
            Q(pk__in=integrantes_actuales) | ~Q(pk__in=asignados)
        ).distinct()
        self.fields["integrantes"].label_from_instance = _etiqueta

        if equipo is not None and not self.is_bound:
            self.initial.setdefault("nombre", equipo.nombre)
            self.initial.setdefault("integrantes", integrantes_actuales)

        for campo in self.fields.values():
            campo.widget.attrs.update({"class": CLASES})


class PartidoEquipoForm(forms.Form):
    equipo_a = forms.ModelChoiceField(
        label="Equipo A", queryset=Equipo.objects.none(),
        empty_label="Elige un equipo",
    )
    equipo_b = forms.ModelChoiceField(
        label="Equipo B", queryset=Equipo.objects.none(),
        empty_label="Elige un equipo",
    )
    fecha_hora = forms.DateTimeField(
        label="Fecha y hora del partido",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
    )
    ronda = forms.CharField(
        label="Ronda o jornada (opcional)",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej.: Jornada 1, Semifinal"}),
    )

    def __init__(self, *args, torneo, **kwargs):
        super().__init__(*args, **kwargs)
        equipos = Equipo.objects.filter(torneo=torneo).order_by("nombre", "pk")
        for campo in ("equipo_a", "equipo_b"):
            self.fields[campo].queryset = equipos
            self.fields[campo].label_from_instance = lambda equipo: equipo.nombre

        for campo in self.fields.values():
            campo.widget.attrs.update({"class": CLASES})