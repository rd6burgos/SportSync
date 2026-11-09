from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0003_solicitudorganizador"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="foto_perfil",
            field=models.ImageField(blank=True, null=True, upload_to="perfiles/", verbose_name="foto de perfil"),
        ),
    ]
