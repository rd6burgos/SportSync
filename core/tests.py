from django.test import TestCase
from django.urls import reverse


class PaginaInicioTests(TestCase):

    def test_inicio_muestra_informacion_de_funciones_y_accesos(self):
        respuesta = self.client.get(reverse("inicio"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Entrena.")
        self.assertContains(respuesta, "Todo lo que necesitas para vivir el deporte")
        self.assertContains(respuesta, "Explora actividades")
        self.assertContains(respuesta, "Inscríbete y participa")
        self.assertContains(respuesta, "Compite en torneos")
        self.assertContains(respuesta, "Organiza encuentros")
        self.assertContains(respuesta, reverse("actividades:catalogo"))
        self.assertContains(respuesta, reverse("actividades:calendario_publico"))
        self.assertContains(respuesta, "¿Aún no tienes cuenta?")
        self.assertContains(respuesta, "Crear mi cuenta")
        self.assertContains(respuesta, reverse("usuarios:registro"))

    def test_usuario_con_sesion_no_ve_invitacion_a_crear_cuenta(self):
        from usuarios.models import Usuario

        usuario = Usuario.objects.create_user(
            "inicio@example.com",
            "clave-segura-123",
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("inicio"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "¿Aún no tienes cuenta?")
        self.assertNotContains(respuesta, "Crear mi cuenta")
