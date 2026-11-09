from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inscripciones.models import Inscripcion
from usuarios.models import Usuario

from .models import Actividad


class DetalleActividadHistoricaTests(TestCase):

    def setUp(self):
        self.organizador = Usuario.objects.create_user(
            "organizador@example.com", "clave-segura-123", rol="organizador"
        )
        self.participante = Usuario.objects.create_user(
            "participante@example.com", "clave-segura-123"
        )
        inicio = timezone.now() + timedelta(days=1)
        self.actividad = Actividad.objects.create(
            nombre="Actividad histórica",
            descripcion="Prueba de detalle histórico",
            deporte="Fútbol",
            ubicacion="Cancha",
            fecha_inicio=inicio,
            fecha_fin=inicio + timedelta(hours=2),
            cupo_maximo=10,
            organizador=self.organizador,
            estado=Actividad.Estado.CANCELADA,
        )

    def detalle_url(self):
        return reverse(
            "actividades:detalle_publico",
            args=[self.actividad.pk],
        )

    def test_organizador_puede_abrir_detalle_de_actividad_cancelada(self):
        self.client.force_login(self.organizador)

        respuesta = self.client.get(self.detalle_url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Esta actividad fue cancelada")
        self.assertContains(respuesta, "como parte del historial")

    def test_participante_confirmado_puede_ver_detalle_finalizado(self):
        self.actividad.estado = Actividad.Estado.FINALIZADA
        self.actividad.save(update_fields=["estado"])
        Inscripcion.objects.create(
            participante=self.participante,
            actividad=self.actividad,
            estado=Inscripcion.Estado.CONFIRMADA,
        )
        self.client.force_login(self.participante)

        respuesta = self.client.get(self.detalle_url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Esta actividad ha finalizado")

    def test_usuario_sin_acceso_no_puede_ver_actividad_historica(self):
        otro_usuario = Usuario.objects.create_user(
            "otro@example.com", "clave-segura-123"
        )
        self.client.force_login(otro_usuario)

        respuesta = self.client.get(self.detalle_url())

        self.assertEqual(respuesta.status_code, 404)

    def test_actividad_cancelada_aparece_en_mis_actividades_del_organizador(self):
        self.client.force_login(self.organizador)

        respuesta = self.client.get(
            reverse("actividades:mis_actividades"),
            {"seccion": "historicas"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.detalle_url())
