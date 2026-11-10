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
        self.assertContains(respuesta, "Gestionar pagos")
        self.assertNotContains(respuesta, "Escanear QR")

    def test_organizador_ve_acceso_a_pagos_y_escaneo_durante_actividad_en_curso(self):
        self.actividad.estado = Actividad.Estado.EN_CURSO
        self.actividad.save(update_fields=["estado"])
        self.client.force_login(self.organizador)

        respuesta = self.client.get(self.detalle_url())

        self.assertContains(respuesta, "Escanear QR")
        self.assertContains(respuesta, reverse("inscripciones:escanear_qr", args=[self.actividad.pk]))
        self.assertContains(respuesta, "Gestionar pagos")
        self.assertContains(respuesta, reverse("inscripciones:panel_pagos"))

    def test_detalle_muestra_navegacion_al_catalogo_y_mis_actividades(self):
        self.actividad.estado = Actividad.Estado.PUBLICADA
        self.actividad.save(update_fields=["estado"])
        self.client.force_login(self.participante)

        respuesta = self.client.get(self.detalle_url())

        self.assertContains(respuesta, reverse("actividades:calendario_publico"))
        self.assertContains(respuesta, reverse("actividades:catalogo"))
        self.assertContains(respuesta, reverse("actividades:mis_actividades"))
        self.assertNotContains(respuesta, "Gestionar pagos")
        self.assertNotContains(respuesta, "Escanear QR")

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


class MisActividadesTests(TestCase):

    def setUp(self):
        self.organizador = Usuario.objects.create_user(
            "organizador-mis-actividades@example.com",
            "clave-segura-123",
            rol="organizador",
        )
        self.participante = Usuario.objects.create_user(
            "participante-mis-actividades@example.com",
            "clave-segura-123",
        )
        self.client.force_login(self.participante)
        inicio = timezone.now() + timedelta(days=2)
        self.actividades = {}
        for nombre, estado in (
            ("Actividad abierta", Actividad.Estado.PUBLICADA),
            ("Actividad cerrada", Actividad.Estado.INSCRIPCION_CERRADA),
            ("Actividad en curso", Actividad.Estado.EN_CURSO),
            ("Actividad cancelada", Actividad.Estado.CANCELADA),
            ("Actividad finalizada", Actividad.Estado.FINALIZADA),
        ):
            actividad = Actividad.objects.create(
                nombre=nombre,
                descripcion="Actividad de prueba",
                deporte="Fútbol",
                ubicacion="Cancha",
                fecha_inicio=inicio,
                fecha_fin=inicio + timedelta(hours=2),
                cupo_maximo=10,
                organizador=self.organizador,
                estado=estado,
            )
            Inscripcion.objects.create(
                participante=self.participante,
                actividad=actividad,
                estado=Inscripcion.Estado.CONFIRMADA,
            )
            self.actividades[nombre] = actividad

    def test_pestana_inscritas_agrupa_actividades_por_estado(self):
        respuesta = self.client.get(reverse("actividades:mis_actividades"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["vista"], "inscritas")
        self.assertContains(respuesta, "Actividades externas")
        self.assertContains(respuesta, "Creadas por mí")
        self.assertContains(respuesta, "En curso")
        self.assertContains(respuesta, "Inscrito")
        self.assertContains(respuesta, "Canceladas")
        self.assertContains(respuesta, "Finalizadas")
        for nombre in self.actividades:
            self.assertContains(respuesta, nombre)

    def test_pestana_creadas_por_mi_solo_muestra_mis_actividades(self):
        creador = Usuario.objects.create_user(
            "creador-actividades@example.com",
            "clave-segura-123",
            rol="organizador",
        )
        self.client.force_login(creador)
        actividades_organizadas = (
            ("Organizada en curso", Actividad.Estado.EN_CURSO),
            ("Organizada próxima", Actividad.Estado.PUBLICADA),
            ("Organizada cancelada", Actividad.Estado.CANCELADA),
            ("Organizada finalizada", Actividad.Estado.FINALIZADA),
        )
        for nombre, estado in actividades_organizadas:
            Actividad.objects.create(
                nombre=nombre,
                descripcion="Actividad organizada de prueba",
                deporte="Fútbol",
                ubicacion="Cancha",
                fecha_inicio=timezone.now() + timedelta(days=2),
                fecha_fin=timezone.now() + timedelta(days=2, hours=2),
                cupo_maximo=10,
                organizador=creador,
                estado=estado,
            )

        respuesta = self.client.get(
            reverse("actividades:mis_actividades"),
            {"vista": "organizadas"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["vista"], "organizadas")
        grupos = {
            grupo["titulo"]: list(grupo["actividades"])
            for grupo in respuesta.context["grupos"]
        }
        self.assertEqual(len(grupos["En curso"]), 1)
        self.assertEqual(len(grupos["Próximas"]), 1)
        self.assertEqual(len(grupos["Canceladas"]), 1)
        self.assertEqual(len(grupos["Finalizadas"]), 1)
        self.assertContains(respuesta, "Organizada en curso")
        self.assertContains(respuesta, "Organizada próxima")
        self.assertContains(respuesta, "Organizada cancelada")
        self.assertContains(respuesta, "Organizada finalizada")
        self.assertContains(respuesta, "Actividades creadas por mí")
        for nombre in self.actividades:
            self.assertNotContains(respuesta, nombre)

    def test_inscripcion_no_confirmada_no_aparece_en_actividades_externas(self):
        no_confirmada = self.actividades["Actividad abierta"]
        Inscripcion.objects.filter(
            participante=self.participante,
            actividad=no_confirmada,
        ).update(estado=Inscripcion.Estado.LISTA_ESPERA)

        respuesta = self.client.get(reverse("actividades:mis_actividades"))

        self.assertNotContains(respuesta, no_confirmada.nombre)
        self.assertContains(respuesta, "Actividad en curso")
