# Etapa 15: registro único de asistencia para QR de un solo uso.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inscripciones", "0003_alter_notificacion_tipo_pago"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Asistencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_registro", models.DateTimeField(auto_now_add=True)),
                ("inscripcion", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="asistencia", to="inscripciones.inscripcion")),
                ("registrado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asistencias_registradas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "asistencia",
                "verbose_name_plural": "asistencias",
                "ordering": ["-fecha_registro"],
            },
        ),
    ]
