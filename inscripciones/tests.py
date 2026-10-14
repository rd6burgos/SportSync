from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from actividades.models import Actividad
from usuarios.models import Usuario

from .models import Inscripcion
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