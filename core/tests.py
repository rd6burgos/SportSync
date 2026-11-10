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
        self.assertContains(respuesta, 'id="carrusel-inicio"')
        self.assertContains(respuesta, 'aria-roledescription="diapositiva"', count=5)
        self.assertContains(respuesta, "wooden-basketball-court-3840x2160-17426.jpg")
        self.assertContains(respuesta, "roger-federer-tennis-player-swiss-player-5k-8k-3840x2160-1801.jpg")
        self.assertContains(respuesta, "paris-summer-3840x2160-13553.jpg")
        self.assertContains(respuesta, "lamine-yamal-fifa-3840x2160-27561.jpg")
        self.assertContains(respuesta, "brazil-football-3840x2160-17323.jpg")
        self.assertContains(respuesta, 'data-carrusel-anterior')
        self.assertContains(respuesta, 'data-carrusel-siguiente')
        self.assertContains(respuesta, "prefers-reduced-motion")
        self.assertContains(respuesta, "650ms")
        html = respuesta.content.decode()
        self.assertLess(html.index('id="carrusel-inicio"'), html.index("Entrena."))
        self.assertContains(respuesta, "object-contain")

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
