from django.test import TestCase
from django.urls import reverse

from .models import Usuario


class PerfilTests(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            "perfil@example.com",
            "clave-segura-123",
            first_name="Nombre",
            last_name="Anterior",
        )
        self.client.force_login(self.usuario)
        self.url = reverse("usuarios:perfil")

    def test_perfil_muestra_campos_editables_de_nombre_y_apellido(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="first_name"')
        self.assertContains(respuesta, 'name="last_name"')
        self.assertContains(respuesta, "Guardar cambios")

    def test_usuario_puede_actualizar_nombre_y_apellido(self):
        respuesta = self.client.post(
            self.url,
            {
                "first_name": "Nuevo nombre",
                "last_name": "Nuevo apellido",
            },
        )

        self.assertRedirects(respuesta, self.url)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nuevo nombre")
        self.assertEqual(self.usuario.last_name, "Nuevo apellido")

    def test_usuario_puede_actualizar_solo_el_nombre(self):
        respuesta = self.client.post(
            self.url,
            {
                "first_name": "Nombre actualizado",
                "last_name": self.usuario.last_name,
            },
        )

        self.assertRedirects(respuesta, self.url)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nombre actualizado")
        self.assertEqual(self.usuario.last_name, "Anterior")