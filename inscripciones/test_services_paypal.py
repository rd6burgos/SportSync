from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .services_paypal import PAYPAL_API_URL, reembolsar_captura_paypal


class ReembolsarCapturaPayPalTests(SimpleTestCase):

    @mock.patch("inscripciones.services_paypal.requests.post")
    @mock.patch("inscripciones.services_paypal.obtener_token_paypal")
    def test_solicita_reembolso_total_con_clave_idempotente(
        self, obtener_token, post
    ):
        obtener_token.return_value = "token-de-prueba"
        respuesta = mock.Mock(status_code=201)
        respuesta.json.return_value = {
            "id": "refund-456",
            "status": "COMPLETED",
        }
        post.return_value = respuesta
        pago = SimpleNamespace(paypal_capture_id="capture-456")

        resultado = reembolsar_captura_paypal(pago)

        self.assertEqual(resultado["id"], "refund-456")
        post.assert_called_once_with(
            f"{PAYPAL_API_URL}/v2/payments/captures/capture-456/refund",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer token-de-prueba",
                "PayPal-Request-Id": "refund-capture-456",
            },
            timeout=10,
        )

    def test_rechaza_pagos_sin_id_de_captura(self):
        pago = SimpleNamespace(paypal_capture_id="")

        with self.assertRaisesMessage(
            ValidationError, "El pago no tiene un ID de captura de PayPal."
        ):
            reembolsar_captura_paypal(pago)
