from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from actividades.models import Actividad
from inscripciones.models import Inscripcion, Pago
from usuarios.models import Usuario

from .models import Equipo, Partido, PartidoEquipo
from .servicios import (
    cancelar_partido,
    crear_partido,
    crear_partido_equipo,
    guardar_equipo,
    participantes_validos,
    registrar_resultado,
    registrar_resultado_equipo,
    tabla_posiciones_equipos,
)

# Un cifrado de contraseñas más rápido solo para las pruebas.
RAPIDO = override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)


@RAPIDO
class BaseTorneoTests(TestCase):

    def setUp(self):
        self.organizador = self.usuario("org", rol="organizador")

        self.otro_organizador = self.usuario("otro", rol="organizador")
        self.ana = self.usuario("ana")
        self.luis = self.usuario("luis")
        self.maria = self.usuario("maria")
        self.nora = self.usuario("nora")

        ahora = timezone.now()
        self.inicio = ahora - timedelta(hours=1)
        self.fin = ahora + timedelta(days=2)

        # Torneo gratuito con inscripciones cerradas y 3 participantes válidos.
        self.torneo = self.crear_torneo(estado="inscripcion_cerrada")
        for u in (self.ana, self.luis, self.maria):
            self.inscribir(u, self.torneo)

        self.cuando = ahora + timedelta(hours=3)

    # --- ayudas ---
    def usuario(self, nombre, rol="participante"):
        return Usuario.objects.create_user(
            f"{nombre}@example.com", "clave-segura-123", rol=rol, first_name=nombre.title()
        )

    def crear_torneo(self, estado="inscripcion_cerrada", costo="0.00", tipo="torneo", organizador=None):
        return Actividad.objects.create(
            nombre="Copa SportSync", descripcion="Prueba", deporte="Ping pong",
            ubicacion="Cancha", tipo=tipo, fecha_inicio=self.inicio, fecha_fin=self.fin,
            cupo_maximo=10, costo=Decimal(costo),
            organizador=organizador or self.organizador, estado=estado,
        )

    def inscribir(self, usuario, actividad, estado="confirmada"):

        return Inscripcion.objects.create(participante=usuario, actividad=actividad, estado=estado)

    def partido(self, a=None, b=None, torneo=None, **extra):
        return crear_partido(
            (torneo or self.torneo).pk, self.organizador,
            a or self.ana, b or self.luis, extra.pop("cuando", self.cuando), extra.pop("ronda", "Jornada 1"),
        )

    def poner_estado(self, estado):
        Actividad.objects.filter(pk=self.torneo.pk).update(estado=estado)


class ParticipantesValidosTests(BaseTorneoTests):

    def test_solo_cuentan_las_inscripciones_confirmadas(self):
        self.inscribir(self.nora, self.torneo, estado="lista_espera")
        self.assertEqual(
            set(participantes_validos(self.torneo)), {self.ana, self.luis, self.maria}
        )

    def test_una_inscripcion_cancelada_deja_de_ser_valida(self):
        Inscripcion.objects.filter(participante=self.ana).update(estado="cancelada")
        self.assertNotIn(self.ana, participantes_validos(self.torneo))

    def test_en_torneo_de_pago_solo_cuenta_el_pago_aprobado(self):
        pago = self.crear_torneo(costo="5.00")
        for usuario, estado in ((self.ana, "aprobado"), (self.luis, "pendiente"), (self.maria, "en_revision")):
            ins = self.inscribir(usuario, pago)
            Pago.objects.create(inscripcion=ins, monto=Decimal("5.00"), estado=estado)
        self.assertEqual(list(participantes_validos(pago)), [self.ana])



class CrearPartidoTests(BaseTorneoTests):

    def test_crea_un_partido_valido(self):
        p = self.partido()
        self.assertEqual((p.estado, p.ronda), ("programado", "Jornada 1"))
        self.assertIsNone(p.marcador_a)

    def test_tambien_se_puede_programar_con_el_torneo_en_curso(self):
        self.poner_estado("en_curso")
        self.assertEqual(Partido.objects.count() + 1, self.partido().pk)

    def test_no_se_programa_si_el_torneo_no_esta_cerrado_ni_en_curso(self):
        for estado in ("borrador", "publicada", "finalizada", "cancelada"):
            self.poner_estado(estado)
            with self.assertRaisesMessage(ValidationError, "Solo se pueden programar partidos"):
                self.partido()
        self.assertEqual(Partido.objects.count(), 0)

    def test_la_actividad_debe_ser_un_torneo(self):
        normal = self.crear_torneo(tipo="actividad")
        with self.assertRaisesMessage(ValidationError, "no es un torneo"):
            crear_partido(normal.pk, self.organizador, self.ana, self.luis, self.cuando)

    def test_un_participante_no_juega_contra_si_mismo(self):
        with self.assertRaisesMessage(ValidationError, "contra sí mismo"):
            self.partido(a=self.ana, b=self.ana)

    def test_exige_inscripcion_valida_para_ambos(self):
        self.inscribir(self.nora, self.torneo, estado="lista_espera")
        with self.assertRaisesMessage(ValidationError, "Nora no tiene una inscripción válida"):
            self.partido(a=self.ana, b=self.nora)


    def test_un_usuario_sin_inscripcion_no_puede_jugar(self):
        extra = self.usuario("extra")
        with self.assertRaisesMessage(ValidationError, "no tiene una inscripción válida"):
            self.partido(a=extra, b=self.ana)

    def test_en_torneo_de_pago_exige_pago_aprobado(self):
        pago = self.crear_torneo(costo="5.00")
        for usuario, estado in ((self.ana, "aprobado"), (self.luis, "pendiente")):
            Pago.objects.create(
                inscripcion=self.inscribir(usuario, pago), monto=Decimal("5.00"), estado=estado
            )
        with self.assertRaisesMessage(ValidationError, "Luis no tiene una inscripción válida"):
            crear_partido(pago.pk, self.organizador, self.ana, self.luis, self.cuando)

    def test_la_fecha_debe_estar_dentro_del_horario_del_torneo(self):
        for fecha in (self.inicio - timedelta(days=1), self.fin + timedelta(days=1)):
            with self.assertRaisesMessage(ValidationError, "dentro del horario del torneo"):
                self.partido(cuando=fecha)

    def test_solo_el_organizador_del_torneo_puede_programar(self):
        with self.assertRaisesMessage(ValidationError, "Solo el organizador"):
            crear_partido(self.torneo.pk, self.otro_organizador, self.ana, self.luis, self.cuando)


class ResultadoTests(BaseTorneoTests):

    def setUp(self):
        super().setUp()
        self.p = self.partido()
        self.poner_estado("en_curso")

    def registrar(self, a=3, b=1, usuario=None):

        return registrar_resultado(self.p.pk, a, b, usuario or self.organizador)

    def test_registra_el_resultado_y_la_trazabilidad(self):
        p = self.registrar(3, 1)
        self.assertEqual((p.estado, p.marcador_a, p.marcador_b), ("jugado", 3, 1))
        self.assertEqual(p.resultado_registrado_por, self.organizador)
        self.assertIsNotNone(p.fecha_resultado)
        self.assertEqual(p.ganador, self.ana)

    def test_el_empate_es_valido_y_no_tiene_ganador(self):
        self.assertIsNone(self.registrar(2, 2).ganador)

    def test_se_puede_corregir_un_resultado(self):
        self.registrar(3, 1)
        p = self.registrar(1, 3)
        self.assertEqual((p.marcador_a, p.marcador_b, p.ganador), (1, 3, self.luis))

    def test_solo_se_registra_con_el_torneo_en_curso(self):
        for estado in ("inscripcion_cerrada", "finalizada", "cancelada"):
            self.poner_estado(estado)
            with self.assertRaisesMessage(ValidationError, "solo se registran mientras el torneo está en curso"):
                self.registrar()
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "programado")

    def test_marcadores_invalidos(self):
        for a, b in ((-1, 0), (0, -5), (1000, 0), (0, 1000)):
            with self.assertRaises(ValidationError):
                self.registrar(a, b)
        for a, b in (("3", 1), (None, 1), (1.5, 1), (True, 1)):
            with self.assertRaisesMessage(ValidationError, "números enteros"):
                self.registrar(a, b)

        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "programado")

    def test_un_partido_cancelado_no_admite_resultado(self):
        self.poner_estado("en_curso")
        Partido.objects.filter(pk=self.p.pk).update(estado="cancelado")
        with self.assertRaisesMessage(ValidationError, "cancelado no admite resultado"):
            self.registrar()

    def test_no_se_registra_si_un_participante_ya_no_es_valido(self):
        Inscripcion.objects.filter(participante=self.ana).update(estado="cancelada")
        with self.assertRaisesMessage(ValidationError, "Ana no tiene una inscripción válida"):
            self.registrar()

    def test_solo_su_organizador_registra_resultados(self):
        with self.assertRaisesMessage(ValidationError, "Solo el organizador"):
            self.registrar(usuario=self.otro_organizador)


class CancelarPartidoTests(BaseTorneoTests):

    def test_cancela_un_partido_programado(self):
        p = self.partido()
        self.assertEqual(cancelar_partido(p.pk, self.organizador).estado, "cancelado")

    def test_no_cancela_un_partido_jugado(self):
        p = self.partido()
        self.poner_estado("en_curso")
        registrar_resultado(p.pk, 1, 0, self.organizador)
        with self.assertRaisesMessage(ValidationError, "no se han jugado"):
            cancelar_partido(p.pk, self.organizador)


    def test_no_cancela_con_el_torneo_finalizado(self):
        p = self.partido()
        self.poner_estado("finalizada")
        with self.assertRaisesMessage(ValidationError, "Ya no se pueden cancelar"):
            cancelar_partido(p.pk, self.organizador)


class RestriccionesDeBaseDeDatosTests(BaseTorneoTests):
    """Las reglas críticas también se protegen en la base de datos."""

    def crear_directo(self, **datos):
        base = dict(torneo=self.torneo, participante_a=self.ana, participante_b=self.luis, fecha_hora=self.cuando)
        base.update(datos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Partido.objects.create(**base)

    def test_no_permite_el_mismo_participante_en_ambos_lados(self):
        self.crear_directo(participante_b=self.ana)

    def test_no_permite_un_solo_marcador(self):
        self.crear_directo(marcador_a=2)

    def test_un_partido_jugado_exige_marcadores(self):
        self.crear_directo(estado="jugado")


class VistasTests(BaseTorneoTests):

    def url(self, nombre, *args):
        return reverse(f"torneos:{nombre}", args=args)

    def test_el_organizador_ve_la_pagina_de_gestion(self):

        self.client.force_login(self.organizador)
        r = self.client.get(self.url("gestionar_partidos", self.torneo.pk))
        self.assertContains(r, "Programar un partido")
        self.assertEqual(r.context["total_validos"], 3)

    def test_permisos_de_la_pagina_de_gestion(self):
        u = self.url("gestionar_partidos", self.torneo.pk)
        self.assertEqual(self.client.get(u).status_code, 302)           # sin sesión
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(u).status_code, 403)           # participante
        self.client.force_login(self.otro_organizador)
        self.assertEqual(self.client.get(u).status_code, 404)           # torneo ajeno

    def test_una_actividad_que_no_es_torneo_da_404(self):
        normal = self.crear_torneo(tipo="actividad")
        self.client.force_login(self.organizador)
        self.assertEqual(self.client.get(self.url("gestionar_partidos", normal.pk)).status_code, 404)

    def test_programar_un_partido_desde_el_formulario(self):
        self.client.force_login(self.organizador)
        r = self.client.post(self.url("crear_partido", self.torneo.pk), {
            "participante_a": self.ana.pk, "participante_b": self.luis.pk,
            "fecha_hora": timezone.localtime(self.cuando).strftime("%Y-%m-%dT%H:%M"),
            "ronda": "Semifinal",
        }, follow=True)
        self.assertContains(r, "Partido programado.")
        self.assertEqual(Partido.objects.get().ronda, "Semifinal")

    def test_el_formulario_solo_ofrece_participantes_validos(self):
        self.inscribir(self.nora, self.torneo, estado="lista_espera")
        self.client.force_login(self.organizador)
        r = self.client.post(self.url("crear_partido", self.torneo.pk), {

            "participante_a": self.nora.pk, "participante_b": self.luis.pk,
            "fecha_hora": timezone.localtime(self.cuando).strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Partido.objects.count(), 0)
        self.assertTrue(r.context["form"].errors)

    def test_los_errores_de_las_reglas_se_muestran_en_el_formulario(self):
        self.client.force_login(self.organizador)
        r = self.client.post(self.url("crear_partido", self.torneo.pk), {
            "participante_a": self.ana.pk, "participante_b": self.ana.pk,
            "fecha_hora": timezone.localtime(self.cuando).strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertContains(r, "contra sí mismo")
        self.assertEqual(Partido.objects.count(), 0)

    def test_registrar_resultado_desde_la_vista(self):
        p = self.partido()
        self.poner_estado("en_curso")
        self.client.force_login(self.organizador)
        r = self.client.post(self.url("registrar_resultado", p.pk), {"marcador_a": "4", "marcador_b": "2"}, follow=True)
        self.assertContains(r, "Resultado guardado.")
        p.refresh_from_db()
        self.assertEqual((p.marcador_a, p.marcador_b), (4, 2))

    def test_marcador_no_numerico_se_rechaza(self):
        p = self.partido()
        self.poner_estado("en_curso")
        self.client.force_login(self.organizador)
        r = self.client.post(self.url("registrar_resultado", p.pk), {"marcador_a": "abc", "marcador_b": ""}, follow=True)
        self.assertContains(r, "marcador numérico")
        p.refresh_from_db()

        self.assertEqual(p.estado, "programado")

    def test_otro_organizador_no_toca_los_partidos_ajenos(self):
        p = self.partido()
        self.poner_estado("en_curso")
        self.client.force_login(self.otro_organizador)
        for nombre, datos in (("registrar_resultado", {"marcador_a": 1, "marcador_b": 0}), ("cancelar_partido", {})):
            self.assertEqual(self.client.post(self.url(nombre, p.pk), datos).status_code, 404)
        p.refresh_from_db()
        self.assertEqual(p.estado, "programado")

    def test_las_acciones_exigen_post(self):
        p = self.partido()
        self.client.force_login(self.organizador)
        for nombre in ("registrar_resultado", "cancelar_partido"):
            self.assertEqual(self.client.get(self.url(nombre, p.pk)).status_code, 405)

    def test_la_pagina_avisa_si_un_participante_dejo_de_ser_valido(self):
        self.partido()
        Inscripcion.objects.filter(participante=self.ana).update(estado="cancelada")
        self.client.force_login(self.organizador)
        r = self.client.get(self.url("gestionar_partidos", self.torneo.pk))
        self.assertContains(r, "ya no tiene una inscripción válida")

    # --- página pública ---
    def test_la_pagina_publica_muestra_partidos_y_resultados(self):
        p = self.partido()
        self.poner_estado("en_curso")
        registrar_resultado(p.pk, 5, 3, self.organizador)
        r = self.client.get(self.url("partidos_publicos", self.torneo.pk))
        self.assertContains(r, "Ana")
        self.assertContains(r, "5 - 3")

        self.assertNotContains(r, "ana@example.com")        # no expone correos

    def test_la_pagina_publica_no_muestra_borradores_ni_actividades_normales(self):
        self.poner_estado("borrador")
        self.assertEqual(self.client.get(self.url("partidos_publicos", self.torneo.pk)).status_code, 302)
        normal = self.crear_torneo(tipo="actividad")
        self.assertEqual(self.client.get(self.url("partidos_publicos", normal.pk)).status_code, 404)

    def test_los_textos_del_usuario_se_escapan(self):
        self.partido(ronda="<script>alert('XSS')</script>")
        r = self.client.get(self.url("partidos_publicos", self.torneo.pk))
        self.assertNotContains(r, "<script>alert('XSS')</script>")
        self.assertContains(r, "&lt;script&gt;")

    def test_el_detalle_del_torneo_enlaza_a_los_partidos(self):
        r = self.client.get(reverse("actividades:detalle_publico", args=[self.torneo.pk]))
        self.assertContains(r, self.url("partidos_publicos", self.torneo.pk))
        normal = self.crear_torneo(tipo="actividad", estado="publicada")
        r = self.client.get(reverse("actividades:detalle_publico", args=[normal.pk]))
        self.assertNotContains(r, "Ver partidos y resultados")

    def test_el_panel_del_organizador_muestra_el_boton_en_torneos(self):
        self.client.force_login(self.organizador)
        r = self.client.get(reverse("actividades:panel_actividades_organizador"))
        self.assertContains(r, self.url("gestionar_partidos", self.torneo.pk))


class EquiposTorneoTests(BaseTorneoTests):

    def crear_equipo(self, nombre, integrantes):
        return guardar_equipo(
            self.torneo.pk,
            self.organizador,
            nombre,
            integrantes,
        )

    def setUp(self):
        super().setUp()
        self.azul = self.crear_equipo("Azul", [self.ana])
        self.rojo = self.crear_equipo("Rojo", [self.luis])
        self.verde = self.crear_equipo("Verde", [self.maria])

    def test_participante_no_puede_asignarse_a_dos_equipos(self):
        with self.assertRaisesMessage(ValidationError, "solo puede pertenecer"):
            self.crear_equipo("Amarillo", [self.ana])

    def test_no_se_aceptan_equipos_repetidos_en_el_mismo_torneo(self):
        with self.assertRaisesMessage(ValidationError, "Ya existe un equipo"):
            self.crear_equipo("azul", [self.maria])

    def test_partido_de_equipos_exige_dos_equipos_del_mismo_torneo(self):
        with self.assertRaisesMessage(ValidationError, "no puede jugar contra sí mismo"):
            crear_partido_equipo(
                self.torneo.pk,
                self.organizador,
                self.azul,
                self.azul,
                self.cuando,
            )

        otro_torneo = self.crear_torneo()
        Inscripcion.objects.create(participante=self.nora, actividad=otro_torneo)
        equipo_ajeno = guardar_equipo(
            otro_torneo.pk, self.organizador, "Visitante", [self.nora]
        )
        with self.assertRaisesMessage(ValidationError, "pertenecer a este torneo"):
            crear_partido_equipo(
                self.torneo.pk,
                self.organizador,
                self.azul,
                equipo_ajeno,
                self.cuando,
            )

    def test_cambiar_plantilla_de_equipo_con_partidos_jugados_se_rechaza(self):
        self.poner_estado("en_curso")
        partido = crear_partido_equipo(
            self.torneo.pk,
            self.organizador,
            self.azul,
            self.rojo,
            self.cuando,
        )
        registrar_resultado_equipo(partido.pk, 2, 0, self.organizador)

        with self.assertRaisesMessage(ValidationError, "ya tiene partidos jugados"):
            guardar_equipo(
                self.torneo.pk,
                self.organizador,
                "Azul",
                [self.maria],
                equipo_id=self.azul.pk,
            )

    def test_tabla_se_recalcula_al_corregir_resultado(self):
        self.poner_estado("en_curso")
        partido = crear_partido_equipo(
            self.torneo.pk,
            self.organizador,
            self.azul,
            self.rojo,
            self.cuando,
        )
        registrar_resultado_equipo(partido.pk, 3, 1, self.organizador)

        tabla = tabla_posiciones_equipos(self.torneo)
        self.assertEqual(tabla[0]["equipo"], self.azul)
        self.assertEqual(tabla[0]["ganados"], 1)
        self.assertEqual(tabla[0]["diferencia_goles"], 2)

        registrar_resultado_equipo(partido.pk, 0, 2, self.organizador)
        tabla = tabla_posiciones_equipos(self.torneo)
        self.assertEqual(tabla[0]["equipo"], self.rojo)
        self.assertEqual(tabla[0]["ganados"], 1)
        self.assertEqual(tabla[1]["equipo"], self.verde)
        self.assertEqual(tabla[2]["equipo"], self.azul)
        self.assertEqual(tabla[2]["perdidos"], 1)

    def test_empate_no_suma_victorias_y_cuenta_goles(self):
        self.poner_estado("en_curso")
        partido = crear_partido_equipo(
            self.torneo.pk,
            self.organizador,
            self.azul,
            self.rojo,
            self.cuando,
        )
        registrar_resultado_equipo(partido.pk, 2, 2, self.organizador)

        filas = {
            fila["equipo"].pk: fila
            for fila in tabla_posiciones_equipos(self.torneo)
        }
        self.assertEqual(filas[self.azul.pk]["ganados"], 0)
        self.assertEqual(filas[self.azul.pk]["empatados"], 1)
        self.assertEqual(filas[self.azul.pk]["goles_favor"], 2)
        self.assertEqual(filas[self.rojo.pk]["empatados"], 1)


class VistasEquiposTests(BaseTorneoTests):

    def url(self, nombre, *args):
        return reverse(f"torneos:{nombre}", args=args)

    def test_pagina_de_gestion_incluye_opcion_de_equipos_sin_quitar_individual(self):
        self.client.force_login(self.organizador)

        respuesta = self.client.get(self.url("gestionar_partidos", self.torneo.pk))

        self.assertContains(respuesta, "Programar un partido")
        self.assertContains(respuesta, "Crear un equipo")
        self.assertContains(respuesta, "Participante A")

    def test_crear_equipos_programar_y_registrar_resultado(self):
        self.client.force_login(self.organizador)
        url_gestion = self.url("gestionar_partidos", self.torneo.pk)
        respuesta = self.client.post(
            self.url("guardar_equipo", self.torneo.pk),
            {"nombre": "Azul", "integrantes": [self.ana.pk]},
            follow=True,
        )
        self.assertContains(respuesta, "Equipo creado.")
        equipo_a = Equipo.objects.get(torneo=self.torneo, nombre="Azul")

        self.client.post(
            self.url("guardar_equipo", self.torneo.pk),
            {"nombre": "Rojo", "integrantes": [self.luis.pk]},
            follow=True,
        )
        equipo_b = Equipo.objects.get(torneo=self.torneo, nombre="Rojo")
        respuesta = self.client.post(
            self.url("crear_partido_equipo", self.torneo.pk),
            {
                "equipo_a": equipo_a.pk,
                "equipo_b": equipo_b.pk,
                "fecha_hora": timezone.localtime(self.cuando).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "ronda": "Final",
            },
            follow=True,
        )
        self.assertContains(respuesta, "Partido entre equipos programado.")
        partido = PartidoEquipo.objects.get(torneo=self.torneo)

        self.poner_estado("en_curso")
        respuesta = self.client.post(
            self.url("registrar_resultado_equipo", partido.pk),
            {"marcador_a": "4", "marcador_b": "2"},
            follow=True,
        )
        self.assertContains(respuesta, "Resultado de equipos guardado.")
        partido.refresh_from_db()
        self.assertEqual((partido.marcador_a, partido.marcador_b), (4, 2))
        self.assertEqual(
            self.client.get(url_gestion).status_code,
            200,
        )

    def test_pagina_publica_muestra_tabla_y_plantillas_de_equipos(self):
        equipo_a = guardar_equipo(
            self.torneo.pk, self.organizador, "Azul", [self.ana]
        )
        equipo_b = guardar_equipo(
            self.torneo.pk, self.organizador, "Rojo", [self.luis]
        )
        self.poner_estado("en_curso")
        partido = crear_partido_equipo(
            self.torneo.pk,
            self.organizador,
            equipo_a,
            equipo_b,
            self.cuando,
        )
        registrar_resultado_equipo(partido.pk, 2, 1, self.organizador)

        respuesta = self.client.get(self.url("partidos_publicos", self.torneo.pk))

        self.assertContains(respuesta, "Tabla de posiciones por equipos")
        self.assertContains(respuesta, "Azul")
        self.assertContains(respuesta, "Ana")
        self.assertContains(respuesta, "2 - 1")
        self.assertContains(respuesta, "Partidos individuales")