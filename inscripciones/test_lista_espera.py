from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from actividades.models import Actividad
from usuarios.models import Usuario

from .lista_espera import promover_lista_espera
from .models import Inscripcion


class ListaEsperaTests(TestCase):

    def setUp(self):
        self.organizador = Usuario.objects.create_user(
            "org@example.com", "clave-segura-123", rol="organizador"
        )
        self.ana = self.usuario("ana")
        self.luis = self.usuario("luis")
        self.maria = self.usuario("maria")
        self.nora = self.usuario("nora")
        ahora = timezone.now() + timedelta(days=10)
        self.actividad = self.crear_actividad(cupo=1, inicio=ahora)

    def usuario(self, nombre):
        return Usuario.objects.create_user(f"{nombre}@example.com", "clave-segura-123")

    def crear_actividad(self, cupo, inicio):
        return Actividad.objects.create(
            nombre="Torneo",

            descripcion="Prueba",
            deporte="Futbol",
            ubicacion="Cancha",
            fecha_inicio=inicio,
            fecha_fin=inicio + timedelta(hours=2),
            cupo_maximo=cupo,
            organizador=self.organizador,
            estado="publicada",
        )

    def inscribirse(self, usuario, actividad=None):
        actividad = actividad or self.actividad
        self.client.force_login(usuario)
        return self.client.post(
            reverse("inscripciones:inscribirse", args=[actividad.pk]), follow=True
        )

    def cancelar(self, usuario, actividad=None):
        actividad = actividad or self.actividad
        inscripcion = Inscripcion.objects.get(participante=usuario, actividad=actividad)
        self.client.force_login(usuario)
        return self.client.post(
            reverse("inscripciones:cancelar", args=[inscripcion.pk]), follow=True
        )

    def estado(self, usuario, actividad=None):
        actividad = actividad or self.actividad
        return (
            Inscripcion.objects.filter(participante=usuario, actividad=actividad)
            .order_by("-pk")
            .first()
            .estado

        )

    # --- CR-03: lista de espera automática -------------------------------

    def test_con_cupo_se_confirma(self):
        self.inscribirse(self.ana)
        self.assertEqual(self.estado(self.ana), "confirmada")

    def test_cupo_lleno_pasa_a_lista_de_espera(self):
        self.inscribirse(self.ana)
        respuesta = self.inscribirse(self.luis)
        self.assertEqual(self.estado(self.luis), "lista_espera")
        self.assertContains(respuesta, "lista de espera")
        self.assertNotContains(respuesta, 'class="segno"')

    def test_nadie_se_salta_la_fila(self):
        # Hay un cupo libre pero Luis ya espera: María no puede pasar delante.
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        Inscripcion.objects.filter(participante=self.ana).update(estado="cancelada")
        self.inscribirse(self.maria)
        self.assertEqual(self.estado(self.maria), "lista_espera")

    # --- CR-04: promoción automática -------------------------------------

    def test_cancelar_promueve_al_primero_de_la_lista(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        self.inscribirse(self.maria)
        self.cancelar(self.ana)
        self.assertEqual(self.estado(self.ana), "cancelada")
        self.assertEqual(self.estado(self.luis), "confirmada")

        self.assertEqual(self.estado(self.maria), "lista_espera")

    def test_el_promovido_ya_ve_su_qr(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        self.cancelar(self.ana)
        inscripcion = Inscripcion.objects.get(participante=self.luis)
        self.client.force_login(self.luis)
        respuesta = self.client.get(
            reverse("inscripciones:detalle", args=[inscripcion.pk])
        )
        self.assertContains(respuesta, 'class="segno"')

    def test_el_orden_lo_da_la_fecha_de_inscripcion(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        self.inscribirse(self.maria)
        # Se fuerza que María se haya inscrito antes que Luis.
        ahora = timezone.now()
        Inscripcion.objects.filter(participante=self.maria).update(
            fecha_inscripcion=ahora - timedelta(hours=2)
        )
        Inscripcion.objects.filter(participante=self.luis).update(
            fecha_inscripcion=ahora - timedelta(hours=1)
        )
        self.cancelar(self.ana)
        self.assertEqual(self.estado(self.maria), "confirmada")
        self.assertEqual(self.estado(self.luis), "lista_espera")

    def test_cancelar_desde_la_lista_no_promueve_a_nadie(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)

        self.inscribirse(self.maria)
        self.cancelar(self.luis)
        self.assertEqual(self.estado(self.ana), "confirmada")
        self.assertEqual(self.estado(self.maria), "lista_espera")

    def test_se_salta_a_los_cancelados_de_la_lista(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        self.inscribirse(self.maria)
        self.cancelar(self.luis)
        self.cancelar(self.ana)
        self.assertEqual(self.estado(self.maria), "confirmada")

    def test_no_se_promueve_a_cuentas_inactivas(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        self.inscribirse(self.maria)
        Usuario.objects.filter(pk=self.luis.pk).update(is_active=False)
        self.cancelar(self.ana)
        self.assertEqual(self.estado(self.luis), "lista_espera")
        self.assertEqual(self.estado(self.maria), "confirmada")

    def test_cancelar_dos_veces_no_promueve_dos_veces(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        self.inscribirse(self.maria)
        self.cancelar(self.ana)
        respuesta = self.cancelar(self.ana)
        self.assertContains(respuesta, "ya estaba cancelada")
        self.assertEqual(self.estado(self.luis), "confirmada")
        self.assertEqual(self.estado(self.maria), "lista_espera")


    def test_nunca_se_supera_el_cupo(self):
        actividad = self.crear_actividad(
            cupo=2, inicio=timezone.now() + timedelta(days=20)
        )
        for usuario in (self.ana, self.luis, self.maria, self.nora):
            self.inscribirse(usuario, actividad)
        self.cancelar(self.ana, actividad)
        self.cancelar(self.luis, actividad)
        confirmadas = Inscripcion.objects.filter(
            actividad=actividad, estado="confirmada"
        )
        self.assertEqual(confirmadas.count(), 2)
        self.assertEqual(self.estado(self.maria, actividad), "confirmada")
        self.assertEqual(self.estado(self.nora, actividad), "confirmada")

    def test_varios_cupos_libres_promueven_varios(self):
        # Si se liberan 2 cupos a la vez, entran los 2 primeros en orden.
        actividad = self.crear_actividad(
            cupo=2, inicio=timezone.now() + timedelta(days=20)
        )
        for usuario in (self.ana, self.luis, self.maria, self.nora):
            self.inscribirse(usuario, actividad)
        Inscripcion.objects.filter(
            actividad=actividad, participante__in=[self.ana, self.luis]
        ).update(estado="cancelada")
        promovidas = promover_lista_espera(actividad)
        self.assertEqual([i.participante for i in promovidas], [self.maria, self.nora])

    def test_actividad_en_curso_no_promueve(self):
        self.inscribirse(self.ana)
        self.inscribirse(self.luis)
        Inscripcion.objects.filter(participante=self.ana).update(estado="cancelada")

        Actividad.objects.filter(pk=self.actividad.pk).update(estado="en_curso")
        self.actividad.refresh_from_db()
        self.assertEqual(promover_lista_espera(self.actividad), [])
        self.assertEqual(self.estado(self.luis), "lista_espera")