from datetime import timedelta
from smtplib import SMTPException
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from actividades.models import Actividad
from usuarios.models import Usuario

from .models import Inscripcion, Notificacion
from .notificaciones import enviar_notificacion


class NotificacionesTests(TestCase):

    def setUp(self):
        self.organizador = Usuario.objects.create_user(
            "org@example.com", "clave-segura-123", rol="organizador"
        )
        self.ana = self.usuario("ana")
        self.luis = self.usuario("luis")
        self.maria = self.usuario("maria")

    def usuario(self, nombre):
        return Usuario.objects.create_user(
            f"{nombre}@example.com", "clave-segura-123", first_name=nombre.title()
        )

    def actividad(self, estado="publicada", cupo=1, inicio_dias=5, duracion_h=2):

        inicio = timezone.now() + timedelta(days=inicio_dias)
        return Actividad.objects.create(
            nombre="Torneo",
            descripcion="Prueba",
            deporte="Futbol",
            ubicacion="Cancha",
            fecha_inicio=inicio,
            fecha_fin=inicio + timedelta(hours=duracion_h),
            cupo_maximo=cupo,
            organizador=self.organizador,
            estado=estado,
        )

    def post(self, usuario, nombre_url, *args, datos=None):
        self.client.force_login(usuario)
        # on_commit solo corre al confirmar la transacción: en las pruebas
        # hay que ejecutarlo a mano.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse(nombre_url, args=args), datos or {}, follow=True)

    def inscribirse(self, usuario, actividad):
        return self.post(usuario, "inscripciones:inscribirse", actividad.pk)

    def cancelar(self, usuario, actividad):
        ins = Inscripcion.objects.get(participante=usuario, actividad=actividad)
        return self.post(usuario, "inscripciones:cancelar", ins.pk)

    def cambiar_estado(self, actividad, estado):
        return self.post(
            self.organizador,
            "actividades:cambiar_estado_actividad",
            actividad.pk,

            datos={"estado": estado},
        )

    def destinatarios(self):
        return sorted(c for m in mail.outbox for c in m.to)

    # --- Inscripción -----------------------------------------------------

    def test_inscripcion_confirmada_envia_correo(self):
        actividad = self.actividad()
        self.inscribirse(self.ana, actividad)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@example.com"])
        self.assertIn("Inscripción confirmada", mail.outbox[0].subject)
        self.assertIn("Hola Ana", mail.outbox[0].body)
        notificacion = Notificacion.objects.get()
        self.assertEqual(notificacion.estado, "enviada")
        self.assertIsNotNone(notificacion.fecha_envio)

    def test_lista_de_espera_envia_correo_distinto(self):
        actividad = self.actividad(cupo=1)
        self.inscribirse(self.ana, actividad)
        mail.outbox.clear()
        self.inscribirse(self.luis, actividad)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("lista de espera", mail.outbox[0].subject)

    def test_inscripcion_rechazada_no_envia_correo(self):
        actividad = self.actividad()
        self.inscribirse(self.ana, actividad)
        mail.outbox.clear()
        self.inscribirse(self.ana, actividad)  # duplicado

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notificacion.objects.count(), 1)

    # --- Promoción -------------------------------------------------------

    def test_promocion_avisa_solo_al_promovido(self):
        actividad = self.actividad(cupo=1)
        self.inscribirse(self.ana, actividad)
        self.inscribirse(self.luis, actividad)
        self.inscribirse(self.maria, actividad)
        mail.outbox.clear()
        self.cancelar(self.ana, actividad)
        self.assertEqual(self.destinatarios(), ["luis@example.com"])
        self.assertIn("Se liberó un cupo", mail.outbox[0].subject)

    # --- Cambios de estado de la actividad --------------------------------

    def preparar_inscritos(self, actividad):
        Inscripcion.objects.create(participante=self.ana, actividad=actividad)
        Inscripcion.objects.create(
            participante=self.luis, actividad=actividad, estado="lista_espera"
        )
        Inscripcion.objects.create(
            participante=self.maria, actividad=actividad, estado="cancelada"
        )

    def test_iniciar_avisa_a_confirmados_y_en_espera(self):
        actividad = self.actividad(estado="inscripcion_cerrada", inicio_dias=-1, duracion_h=72)
        self.preparar_inscritos(actividad)
        respuesta = self.cambiar_estado(actividad, "en_curso")
        self.assertEqual(self.destinatarios(), ["ana@example.com", "luis@example.com"])
        self.assertIn("ha comenzado", mail.outbox[0].subject)

        self.assertContains(respuesta, "Se notificó por correo a 2 inscrito(s)")

    def test_finalizar_avisa_a_los_inscritos(self):
        actividad = self.actividad(estado="en_curso", inicio_dias=-2, duracion_h=1)
        self.preparar_inscritos(actividad)
        self.cambiar_estado(actividad, "finalizada")
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("ha finalizado", mail.outbox[0].subject)

    def test_cancelar_actividad_avisa_a_los_inscritos(self):
        actividad = self.actividad()
        self.preparar_inscritos(actividad)
        self.cambiar_estado(actividad, "cancelada")
        self.assertEqual(self.destinatarios(), ["ana@example.com", "luis@example.com"])
        self.assertIn("Actividad cancelada", mail.outbox[0].subject)

    def test_cerrar_inscripciones_no_envia_correos(self):
        actividad = self.actividad()
        self.preparar_inscritos(actividad)
        self.cambiar_estado(actividad, "inscripcion_cerrada")
        self.assertEqual(len(mail.outbox), 0)

    def test_transicion_invalida_no_envia_correos(self):
        actividad = self.actividad()  # publicada -> en_curso no está permitido
        self.preparar_inscritos(actividad)
        respuesta = self.cambiar_estado(actividad, "en_curso")
        self.assertContains(respuesta, "No se permite ese cambio de estado")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_el_organizador_no_recibe_correo(self):
        actividad = self.actividad()

        self.preparar_inscritos(actividad)
        self.cambiar_estado(actividad, "cancelada")
        self.assertNotIn("org@example.com", self.destinatarios())

    # --- Fallos de envío ---------------------------------------------------

    def test_un_correo_fallido_no_rompe_la_inscripcion_y_queda_registrado(self):
        actividad = self.actividad()
        with mock.patch(
            "inscripciones.notificaciones.send_mail",
            side_effect=SMTPException("servidor caído"),
        ):
            respuesta = self.inscribirse(self.ana, actividad)

        self.assertContains(respuesta, "Te has inscrito correctamente")
        self.assertTrue(Inscripcion.objects.filter(participante=self.ana).exists())
        notificacion = Notificacion.objects.get()
        self.assertEqual(notificacion.estado, "fallida")
        self.assertIn("servidor caído", notificacion.error)
        self.assertEqual(len(mail.outbox), 0)

    def test_reintento_de_una_notificacion_fallida(self):
        actividad = self.actividad()
        with mock.patch(
            "inscripciones.notificaciones.send_mail", side_effect=SMTPException("caído")
        ):
            self.inscribirse(self.ana, actividad)
        notificacion = Notificacion.objects.get()
        self.assertEqual(notificacion.estado, "fallida")

        enviar_notificacion(notificacion.pk)
        notificacion.refresh_from_db()

        self.assertEqual(notificacion.estado, "enviada")
        self.assertEqual(notificacion.error, "")
        self.assertEqual(len(mail.outbox), 1)

    def test_una_notificacion_enviada_no_se_reenvia(self):
        actividad = self.actividad()
        self.inscribirse(self.ana, actividad)
        notificacion = Notificacion.objects.get()
        enviar_notificacion(notificacion.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_si_la_operacion_se_deshace_no_se_envia_correo(self):
        actividad = self.actividad()
        from django.db import transaction

        class Deshacer(Exception):
            pass

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    ins = Inscripcion.objects.create(participante=self.ana, actividad=actividad)
                    from .notificaciones import notificar_inscripcion
                    notificar_inscripcion(ins)
                    raise Deshacer()
            except Deshacer:
                pass

        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)