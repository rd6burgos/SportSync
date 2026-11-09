from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from actividades.models import Actividad
from usuarios.models import Usuario

from .models import Asistencia, Inscripcion, Pago
from .validaciones import conflicto_de_horario, esta_inscrito


class ValidacionInscripcionTests(TestCase):

    def setUp(self):
        self.organizador = Usuario.objects.create_user(
            "org@example.com", "clave-segura-123", rol="organizador"
        )
        self.ana = Usuario.objects.create_user("ana@example.com", "clave-segura-123")
        self.luis = Usuario.objects.create_user("luis@example.com", "clave-segura-123")
        # Dentro de 10 días a las 10:00 como punto de referencia.
        self.base = (timezone.now() + timedelta(days=10)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

    def actividad(self, nombre, inicio_h, fin_h, estado="publicada", cupo=10):
        return Actividad.objects.create(
            nombre=nombre,
            descripcion="Prueba",
            deporte="Futbol",
            ubicacion="Cancha",
            fecha_inicio=self.base + timedelta(hours=inicio_h),
            fecha_fin=self.base + timedelta(hours=fin_h),
            cupo_maximo=cupo,
            organizador=self.organizador,
            estado=estado,
        )

    def inscribir(self, usuario, actividad, estado="confirmada"):
        return Inscripcion.objects.create(
            participante=usuario, actividad=actividad, estado=estado
        )

    def intentar(self, usuario, actividad):
        self.client.force_login(usuario)
        return self.client.post(
            reverse("inscripciones:inscribirse", args=[actividad.pk]), follow=True










            
        )

    # --- Regla de solapamiento -------------------------------------------

    def test_solapamiento_parcial_se_rechaza(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 1, 3)
        self.inscribir(self.ana, a)
        respuesta = self.intentar(self.ana, b)
        self.assertContains(respuesta, "el horario choca")
        self.assertContains(respuesta, "«A»")
        self.assertFalse(esta_inscrito(self.ana, b))

    def test_actividad_contenida_en_otra_se_rechaza(self):
        grande = self.actividad("Grande", 0, 6)
        chica = self.actividad("Chica", 2, 3)
        self.inscribir(self.ana, grande)
        self.assertIsNotNone(conflicto_de_horario(self.ana, chica))

    def test_actividad_que_contiene_a_otra_se_rechaza(self):
        chica = self.actividad("Chica", 2, 3)
        grande = self.actividad("Grande", 0, 6)
        self.inscribir(self.ana, chica)
        self.assertIsNotNone(conflicto_de_horario(self.ana, grande))

    def test_mismo_horario_exacto_se_rechaza(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 0, 2)
        self.inscribir(self.ana, a)
        self.assertIsNotNone(conflicto_de_horario(self.ana, b))

    def test_borde_exacto_no_es_conflicto(self):
        # A termina a las 12:00 y B empieza a las 12:00.
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 2, 4)
        self.inscribir(self.ana, a)
        self.assertIsNone(conflicto_de_horario(self.ana, b))
        respuesta = self.intentar(self.ana, b)
        self.assertTrue(esta_inscrito(self.ana, b))
        self.assertEqual(respuesta.status_code, 200)

    def test_horarios_separados_no_chocan(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 5, 7)
        self.inscribir(self.ana, a)
        self.assertIsNone(conflicto_de_horario(self.ana, b))











    # --- Qué inscripciones cuentan ---------------------------------------

    def test_inscripcion_cancelada_no_genera_conflicto(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 1, 3)
        self.inscribir(self.ana, a, estado="cancelada")
        self.assertIsNone(conflicto_de_horario(self.ana, b))

    def test_actividad_cancelada_no_genera_conflicto(self):
        a = self.actividad("A", 0, 2, estado="cancelada")
        b = self.actividad("B", 1, 3)
        self.inscribir(self.ana, a)
        self.assertIsNone(conflicto_de_horario(self.ana, b))

    def test_inscripcion_de_otro_usuario_no_genera_conflicto(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 1, 3)
        self.inscribir(self.luis, a)
        self.assertIsNone(conflicto_de_horario(self.ana, b))

    def test_lista_de_espera_cuenta_como_activa(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 1, 3)
        self.inscribir(self.ana, a, estado="lista_espera")
        self.assertIsNotNone(conflicto_de_horario(self.ana, b))

    def test_reinscripcion_tras_cancelar_es_posible(self):
        a = self.actividad("A", 0, 2)
        inscripcion = self.inscribir(self.ana, a)
        inscripcion.estado = "cancelada"
        inscripcion.save()
        self.intentar(self.ana, a)
        self.assertEqual(
            Inscripcion.objects.filter(participante=self.ana, actividad=a)
            .exclude(estado="cancelada")
            .count(),
            1,
        )











    # --- Duplicados ------------------------------------------------------

    def test_duplicado_se_rechaza_y_no_crea_otra_fila(self):
        a = self.actividad("A", 0, 2)
        self.intentar(self.ana, a)
        respuesta = self.intentar(self.ana, a)
        self.assertContains(respuesta, "Ya estás inscrito")
        self.assertEqual(Inscripcion.objects.filter(participante=self.ana).count(), 1)

    # --- Mensaje y orden de reglas ---------------------------------------

    def test_el_rechazo_no_crea_inscripcion(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 1, 3)
        self.inscribir(self.ana, a)
        self.intentar(self.ana, b)
        self.assertEqual(Inscripcion.objects.filter(participante=self.ana).count(), 1)

    def test_conflicto_se_detecta_aunque_la_actividad_este_llena(self):
        a = self.actividad("A", 0, 2)
        b = self.actividad("B", 1, 3, cupo=1)
        self.inscribir(self.ana, a)
        self.inscribir(self.luis, b)
        respuesta = self.intentar(self.ana, b)
        self.assertContains(respuesta, "el horario choca")
























class EscaneoQRTests(TestCase):

    def setUp(self):
        self.organizador = Usuario.objects.create_user(
            "organizador-qr@example.com", "clave-segura-123", rol="organizador"
        )
        self.otro_organizador = Usuario.objects.create_user(
            "otro-org-qr@example.com", "clave-segura-123", rol="organizador"
        )
        self.participante = Usuario.objects.create_user(
            "participante-qr@example.com", "clave-segura-123"
        )
        inicio = timezone.now() + timedelta(hours=1)
        self.actividad = Actividad.objects.create(
            nombre="Actividad QR",
            descripcion="Prueba de escaneo",
            deporte="Fútbol",
            ubicacion="Cancha",
            fecha_inicio=inicio,
            fecha_fin=inicio + timedelta(hours=2),
            cupo_maximo=10,
            organizador=self.organizador,
            estado=Actividad.Estado.EN_CURSO,
        )
        self.inscripcion = Inscripcion.objects.create(
            participante=self.participante,
            actividad=self.actividad,
            estado=Inscripcion.Estado.CONFIRMADA,
        )
        self.client.force_login(self.organizador)
        self.url = reverse("inscripciones:validar_qr", args=[self.actividad.pk])

    def test_qr_valido_registra_asistencia(self):
        respuesta = self.client.post(self.url, {"token": str(self.inscripcion.qr_token)})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["ok"])
        self.assertTrue(Asistencia.objects.filter(inscripcion=self.inscripcion).exists())

    def test_qr_no_puede_usarse_dos_veces(self):
        self.client.post(self.url, {"token": str(self.inscripcion.qr_token)})
        respuesta = self.client.post(self.url, {"token": str(self.inscripcion.qr_token)})
        self.assertEqual(respuesta.status_code, 409)
        self.assertFalse(respuesta.json()["ok"])
        self.assertEqual(Asistencia.objects.filter(inscripcion=self.inscripcion).count(), 1)

    def test_qr_de_otra_actividad_es_rechazado(self):
        otra = Actividad.objects.create(
            nombre="Otra actividad", descripcion="Prueba", deporte="Tenis",
            ubicacion="Cancha 2", fecha_inicio=self.actividad.fecha_inicio,
            fecha_fin=self.actividad.fecha_fin, cupo_maximo=10,
            organizador=self.organizador, estado=Actividad.Estado.EN_CURSO,
        )
        respuesta = self.client.post(
            reverse("inscripciones:validar_qr", args=[otra.pk]),
            {"token": str(self.inscripcion.qr_token)},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Asistencia.objects.exists())

    def test_no_permite_escanear_si_actividad_no_esta_en_curso(self):
        self.actividad.estado = Actividad.Estado.PUBLICADA
        self.actividad.save(update_fields=["estado"])
        respuesta = self.client.post(self.url, {"token": str(self.inscripcion.qr_token)})
        self.assertEqual(respuesta.status_code, 409)
        self.assertFalse(Asistencia.objects.exists())

    def test_rechaza_token_invalido(self):
        respuesta = self.client.post(self.url, {"token": "esto-no-es-un-uuid"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Asistencia.objects.exists())

    def test_organizador_no_puede_escanear_actividad_ajena(self):
        otra = Actividad.objects.create(
            nombre="Privada", descripcion="Prueba", deporte="Tenis",
            ubicacion="Cancha 2", fecha_inicio=self.actividad.fecha_inicio,
            fecha_fin=self.actividad.fecha_fin, cupo_maximo=10,
            organizador=self.otro_organizador, estado=Actividad.Estado.EN_CURSO,
        )
        respuesta = self.client.post(
            reverse("inscripciones:validar_qr", args=[otra.pk]),
            {"token": str(self.inscripcion.qr_token)},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Asistencia.objects.exists())

    def test_pago_pendiente_no_permite_registrar_asistencia(self):
        Pago.objects.create(inscripcion=self.inscripcion, monto="10.00")
        respuesta = self.client.post(self.url, {"token": str(self.inscripcion.qr_token)})
        self.assertEqual(respuesta.status_code, 409)
        self.assertFalse(Asistencia.objects.exists())
