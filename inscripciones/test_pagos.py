from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from actividades.models import Actividad
from usuarios.models import Usuario

from .models import Inscripcion, Notificacion, Pago


class PagosPresencialesTests(TestCase):

    def setUp(self):
        self.organizador = Usuario.objects.create_user(
            "org@example.com", "clave-segura-123", rol="organizador"
        )
        self.otro_organizador = Usuario.objects.create_user(
            "otro@example.com", "clave-segura-123", rol="organizador"
        )
        self.ana = self.usuario("ana")
        self.luis = self.usuario("luis")
        self.maria = self.usuario("maria")
        self.de_pago = self.actividad(costo="5.00", cupo=1)
        self.gratis = self.actividad(costo="0.00", cupo=5, dias=20)

    def usuario(self, nombre):
        return Usuario.objects.create_user(
            f"{nombre}@example.com", "clave-segura-123", first_name=nombre.title()

        )

    def actividad(self, costo, cupo, dias=5, estado="publicada"):
        inicio = timezone.now() + timedelta(days=dias)
        return Actividad.objects.create(
            nombre=f"Torneo {costo}",
            descripcion="Prueba",
            deporte="Futbol",
            ubicacion="Cancha",
            fecha_inicio=inicio,
            fecha_fin=inicio + timedelta(hours=2),
            cupo_maximo=cupo,
            costo=Decimal(costo),
            organizador=self.organizador,
            estado=estado,
        )

    def hacer_post(self, usuario, nombre_url, *args, datos=None):
        self.client.force_login(usuario)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse(nombre_url, args=args), datos or {}, follow=True
            )

    def inscribirse(self, usuario, actividad):
        return self.hacer_post(usuario, "inscripciones:inscribirse", actividad.pk)

    def pago_de(self, usuario, actividad):
        return Pago.objects.get(
            inscripcion__participante=usuario, inscripcion__actividad=actividad
        )


    def mover(self, pago, estado, usuario=None):
        return self.hacer_post(
            usuario or self.organizador,
            "inscripciones:cambiar_estado_pago",
            pago.pk,
            datos={"estado": estado},
        )

    def ver_inscripcion(self, usuario, actividad):
        ins = Inscripcion.objects.get(participante=usuario, actividad=actividad)
        self.client.force_login(usuario)
        return self.client.get(reverse("inscripciones:detalle", args=[ins.pk]))

    # --- Creación del pago -------------------------------------------------

    def test_actividad_de_pago_crea_pago_pendiente(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        self.assertEqual(pago.estado, "pendiente")
        self.assertEqual(pago.monto, Decimal("5.00"))
        self.assertEqual(pago.metodo, "")

    def test_actividad_gratuita_no_crea_pago(self):
        self.inscribirse(self.ana, self.gratis)
        self.assertEqual(Pago.objects.count(), 0)

    def test_lista_de_espera_tambien_tiene_pago_pendiente(self):
        self.inscribirse(self.ana, self.de_pago)
        self.inscribirse(self.luis, self.de_pago)
        self.assertEqual(self.pago_de(self.luis, self.de_pago).estado, "pendiente")
        self.assertEqual(
            Inscripcion.objects.get(participante=self.luis).estado, "lista_espera"

        )

    # --- QR según el pago --------------------------------------------------

    def test_el_qr_se_oculta_hasta_aprobar_el_pago(self):
        self.inscribirse(self.ana, self.de_pago)
        respuesta = self.ver_inscripcion(self.ana, self.de_pago)
        self.assertNotContains(respuesta, 'class="segno"')
        self.assertContains(respuesta, "cuando tu pago sea aprobado")

        pago = self.pago_de(self.ana, self.de_pago)
        self.mover(pago, "en_revision")
        self.assertNotContains(self.ver_inscripcion(self.ana, self.de_pago), 'class="segno"')

        self.mover(pago, "aprobado")
        self.assertContains(self.ver_inscripcion(self.ana, self.de_pago), 'class="segno"')

    def test_actividad_gratuita_muestra_el_qr_de_inmediato(self):
        self.inscribirse(self.ana, self.gratis)
        self.assertContains(self.ver_inscripcion(self.ana, self.gratis), 'class="segno"')

    # --- Flujo del organizador ---------------------------------------------

    def test_flujo_pendiente_revision_aprobado(self):
        self.inscribirse(self.ana, self.de_pago)
        mail.outbox.clear()
        pago = self.pago_de(self.ana, self.de_pago)

        self.mover(pago, "en_revision")
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "en_revision")
        self.assertEqual(pago.metodo, "presencial")

        self.assertEqual(pago.revisado_por, self.organizador)
        self.assertEqual(len(mail.outbox), 0)

        self.mover(pago, "aprobado")
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "aprobado")
        self.assertIsNotNone(pago.fecha_pago)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@example.com"])
        self.assertIn("Pago aprobado", mail.outbox[0].subject)

    def test_no_se_aprueba_directo_desde_pendiente(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        respuesta = self.mover(pago, "aprobado")
        self.assertContains(respuesta, "No se puede pasar un pago pendiente a aprobado")
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "pendiente")

    def test_estados_que_el_organizador_no_puede_asignar(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        for estado in ("cancelado", "pendiente", "inventado", ""):
            respuesta = self.mover(pago, estado)
            self.assertContains(respuesta, "no se puede asignar")
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "pendiente")

    def test_un_pago_rechazado_ya_no_cambia(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        self.mover(pago, "rechazado")

        respuesta = self.mover(pago, "aprobado")
        self.assertContains(respuesta, "No se puede pasar un pago rechazado")

    def test_no_se_gestiona_el_pago_de_la_lista_de_espera(self):
        self.inscribirse(self.ana, self.de_pago)
        self.inscribirse(self.luis, self.de_pago)
        pago = self.pago_de(self.luis, self.de_pago)
        respuesta = self.mover(pago, "en_revision")
        self.assertContains(respuesta, "no está confirmada")
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "pendiente")

    def test_no_se_gestionan_pagos_de_una_actividad_finalizada(self):
        self.inscribirse(self.ana, self.de_pago)
        Actividad.objects.filter(pk=self.de_pago.pk).update(estado="finalizada")
        pago = self.pago_de(self.ana, self.de_pago)
        respuesta = self.mover(pago, "en_revision")
        self.assertContains(respuesta, "ya finalizó o fue cancelada")

    # --- Rechazo: cancela, libera el cupo y promueve -----------------------

    def test_rechazar_cancela_la_inscripcion_y_promueve_al_siguiente(self):
        self.inscribirse(self.ana, self.de_pago)
        self.inscribirse(self.luis, self.de_pago)
        self.inscribirse(self.maria, self.de_pago)
        mail.outbox.clear()

        self.mover(self.pago_de(self.ana, self.de_pago), "rechazado")

        self.assertEqual(self.pago_de(self.ana, self.de_pago).estado, "rechazado")
        self.assertEqual(
            Inscripcion.objects.get(participante=self.ana).estado, "cancelada"

        )
        self.assertEqual(
            Inscripcion.objects.get(participante=self.luis).estado, "confirmada"
        )
        self.assertEqual(
            Inscripcion.objects.get(participante=self.maria).estado, "lista_espera"
        )
        destinatarios = sorted(c for m in mail.outbox for c in m.to)
        self.assertEqual(destinatarios, ["ana@example.com", "luis@example.com"])

    def test_al_promover_a_una_actividad_de_pago_el_correo_menciona_el_costo(self):
        self.inscribirse(self.ana, self.de_pago)
        self.inscribirse(self.luis, self.de_pago)
        mail.outbox.clear()
        self.mover(self.pago_de(self.ana, self.de_pago), "rechazado")
        correo_luis = next(m for m in mail.outbox if m.to == ["luis@example.com"])
        self.assertIn("$5.00", correo_luis.body)
        self.assertIn("pago aparece como pendiente", correo_luis.body)

    def test_el_correo_de_inscripcion_con_costo_avisa_del_pago(self):
        self.inscribirse(self.ana, self.de_pago)
        self.assertIn("$5.00", mail.outbox[0].body)

    # --- Cancelación por el participante ------------------------------------

    def test_cancelar_la_inscripcion_cancela_el_pago(self):
        self.inscribirse(self.ana, self.de_pago)
        ins = Inscripcion.objects.get(participante=self.ana)
        self.hacer_post(self.ana, "inscripciones:cancelar", ins.pk)
        self.assertEqual(self.pago_de(self.ana, self.de_pago).estado, "cancelado")

    def test_cancelar_con_pago_aprobado_deja_el_pago_cancelado(self):

        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        self.mover(pago, "en_revision")
        self.mover(pago, "aprobado")
        ins = Inscripcion.objects.get(participante=self.ana)
        self.hacer_post(self.ana, "inscripciones:cancelar", ins.pk)
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "cancelado")
        self.assertIsNotNone(pago.fecha_pago)  # el registro del cobro se conserva

    # --- Permisos -----------------------------------------------------------

    def test_otro_organizador_no_puede_gestionar_el_pago(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        self.client.force_login(self.otro_organizador)
        respuesta = self.client.post(
            reverse("inscripciones:cambiar_estado_pago", args=[pago.pk]),
            {"estado": "en_revision"},
        )
        self.assertEqual(respuesta.status_code, 404)
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "pendiente")

    def test_un_participante_no_puede_gestionar_pagos(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        self.client.force_login(self.ana)
        respuesta = self.client.post(
            reverse("inscripciones:cambiar_estado_pago", args=[pago.pk]),
            {"estado": "aprobado"},
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.client.get(reverse("inscripciones:panel_pagos")).status_code, 403)

    def test_cambiar_el_estado_exige_post(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        self.client.force_login(self.organizador)
        respuesta = self.client.get(
            reverse("inscripciones:cambiar_estado_pago", args=[pago.pk])
        )
        self.assertEqual(respuesta.status_code, 405)

    # --- Panel ---------------------------------------------------------------

    def test_el_panel_muestra_solo_pagos_por_gestionar_de_mis_actividades(self):
        self.inscribirse(self.ana, self.de_pago)       # confirmada, pendiente
        self.inscribirse(self.luis, self.de_pago)      # lista de espera: no aparece
        ajena = Actividad.objects.create(
            nombre="Ajena", descripcion="x", deporte="Tenis", ubicacion="L",
            fecha_inicio=timezone.now() + timedelta(days=9),
            fecha_fin=timezone.now() + timedelta(days=9, hours=2),
            cupo_maximo=5, costo=Decimal("3.00"),
            organizador=self.otro_organizador, estado="publicada",
        )
        self.inscribirse(self.maria, ajena)

        self.client.force_login(self.organizador)
        respuesta = self.client.get(reverse("inscripciones:panel_pagos"))
        self.assertContains(respuesta, "ana@example.com")
        self.assertNotContains(respuesta, "luis@example.com")
        self.assertNotContains(respuesta, "maria@example.com")


    def test_el_panel_filtra_por_estado(self):
        self.inscribirse(self.ana, self.de_pago)
        pago = self.pago_de(self.ana, self.de_pago)
        self.mover(pago, "en_revision")
        self.mover(pago, "aprobado")
        self.client.force_login(self.organizador)
        por_gestionar = self.client.get(reverse("inscripciones:panel_pagos"))
        aprobados = self.client.get(reverse("inscripciones:panel_pagos"), {"filtro": "aprobado"})
        self.assertNotContains(por_gestionar, "ana@example.com")
        self.assertContains(aprobados, "ana@example.com")

    def test_un_filtro_invalido_usa_el_de_por_defecto(self):
        self.client.force_login(self.organizador)
        respuesta = self.client.get(reverse("inscripciones:panel_pagos"), {"filtro": "xyz"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["filtro"], "gestionar")

    def test_el_pago_nuevo_de_una_actividad_no_cambia_si_cambia_el_costo(self):
        self.inscribirse(self.ana, self.de_pago)
        Actividad.objects.filter(pk=self.de_pago.pk).update(costo=Decimal("9.00"))
        self.assertEqual(self.pago_de(self.ana, self.de_pago).monto, Decimal("5.00"))