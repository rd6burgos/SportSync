from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Usuario, SolicitudOrganizador







class RegistroForm(UserCreationForm):
    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        required=True,
    )

    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
    )










    class Meta:
        model = Usuario
        fields = ("first_name", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe una cuenta con este correo electrónico."
            )

        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"

        for field in self.fields.values():
            field.widget.attrs.update({
                "class": (
                    "w-full rounded-lg border border-slate-300 "
                    "bg-white px-4 py-3 text-slate-900 "
                    "focus:outline-none focus:ring-2 focus:ring-blue-600"
                ),
            })

        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"










class SolicitudOrganizadorForm(forms.ModelForm):
    class Meta:
        model = SolicitudOrganizador
        fields = ("motivo",)
        labels = {
            "motivo": "¿Por qué quieres ser organizador?",
        }
        widgets = {
            "motivo": forms.Textarea(attrs={
                "rows": 4,
                "maxlength": 1000,
                "placeholder": "Cuéntanos qué actividades te gustaría organizar.",
                "class": (
                    "w-full rounded-lg border border-slate-300 "
                    "bg-white px-4 py-3 text-slate-900 "
                    "focus:outline-none focus:ring-2 focus:ring-blue-600"
                ),
            }),
        }