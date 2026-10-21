import requests
from django.conf import settings
from django.core.exceptions import ValidationError

PAYPAL_API_URL = "https://api-m.sandbox.paypal.com"


def obtener_token_paypal():
    client_id = getattr(settings, "PAYPAL_CLIENT_ID", "")
    client_secret = getattr(settings, "PAYPAL_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise ValidationError("Las credenciales de PayPal Sandbox no están configuradas.")

    response = requests.post(
        f"{PAYPAL_API_URL}/v1/oauth2/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
    if response.status_code != 200:
        raise ValidationError("No se pudo autenticar con PayPal.")

    return response.json().get("access_token")


def crear_orden_paypal(pago):
    access_token = obtener_token_paypal()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {
                    "currency_code": "USD",
                    "value": f"{pago.monto:.2f}",
                },
                "description": f"Inscripción: {pago.inscripcion.actividad.nombre}",
            }
        ],
    }
    response = requests.post(
        f"{PAYPAL_API_URL}/v2/checkout/orders",
        json=payload,
        headers=headers,
        timeout=10,
    )

    if response.status_code not in (200, 201):
        raise ValidationError("Error al crear la orden en PayPal.")

    data = response.json()
    pago.paypal_order_id = data["id"]
    pago.save(update_fields=["paypal_order_id"])
    return data["id"]


def capturar_orden_paypal(order_id, pago):
    access_token = obtener_token_paypal()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    response = requests.post(
        f"{PAYPAL_API_URL}/v2/checkout/orders/{order_id}/capture",
        headers=headers,
        timeout=10,
    )

    if response.status_code not in (200, 201):
        raise ValidationError("No se pudo procesar la captura del pago en PayPal.")

    data = response.json()
    if data.get("status") == "COMPLETED":
        capture_id = data["purchase_units"][0]["payments"]["captures"][0]["id"]
        return capture_id
    else:
        raise ValidationError("El pago en PayPal no fue completado.")