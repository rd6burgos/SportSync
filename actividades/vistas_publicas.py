import calendar
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_safe

from .models import Actividad


ESTADOS_PUBLICOS = (

    Actividad.Estado.PUBLICADA,
    Actividad.Estado.INSCRIPCION_CERRADA,
    Actividad.Estado.EN_CURSO,

)

MESES = (
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


def actividades_publicas():
    return Actividad.objects.filter(
        estado__in=ESTADOS_PUBLICOS,
    )


def leer_entero(valor, predeterminado, minimo, maximo):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return predeterminado

    if minimo <= numero <= maximo:
        return numero

    return predeterminado


@require_safe
def calendario_publico(request):
    hoy = timezone.localdate()

    anio = leer_entero(
        request.GET.get("anio"),
        hoy.year,
        1901,
        2099,
    )

    mes = leer_entero(
        request.GET.get("mes"),
        hoy.month,
        1,
        12,
    )

    deporte = request.GET.get("deporte", "").strip()[:100]
    ubicacion = request.GET.get("ubicacion", "").strip()[:250]
    tipo = request.GET.get("tipo", "").strip()

    if tipo not in Actividad.Tipo.values:
        tipo = ""

    calendario = calendar.Calendar(firstweekday=0)
    semanas_fechas = calendario.monthdatescalendar(anio, mes)

    primer_dia_visible = semanas_fechas[0][0]
    ultimo_dia_visible = semanas_fechas[-1][-1]

    zona = timezone.get_current_timezone()

    inicio_visible = timezone.make_aware(
        datetime.combine(primer_dia_visible, time.min),
        zona,
    )

    fin_visible = timezone.make_aware(
        datetime.combine(
            ultimo_dia_visible + timedelta(days=1),
            time.min,
        ),
        zona,
    )

    # Incluye las actividades que se superponen con el calendario.
    actividades = actividades_publicas().filter(
        fecha_inicio__lt=fin_visible,
        fecha_fin__gt=inicio_visible,
    )

    if deporte:
        actividades = actividades.filter(
            deporte__icontains=deporte,
        )

    if ubicacion:
        actividades = actividades.filter(
            ubicacion__icontains=ubicacion,
        )

    if tipo:
        actividades = actividades.filter(tipo=tipo)

    actividades = list(
        actividades.order_by("fecha_inicio", "pk")
    )

    actividades_por_dia = {
        dia: []
        for semana in semanas_fechas
        for dia in semana
    }

    for actividad in actividades:
        inicio_local = timezone.localtime(
            actividad.fecha_inicio,
            zona,
        )

        # Si termina a medianoche, no ocupa el día siguiente.
        fin_local = timezone.localtime(
            actividad.fecha_fin - timedelta(microseconds=1),
            zona,
        )

        primer_dia = max(
            inicio_local.date(),
            primer_dia_visible,
        )

        ultimo_dia = min(
            fin_local.date(),
            ultimo_dia_visible,
        )

        dia = primer_dia

        while dia <= ultimo_dia:
            actividades_por_dia[dia].append({
                "actividad": actividad,
                "comienza": dia == inicio_local.date(),
            })

            dia += timedelta(days=1)

    semanas = []

    for semana in semanas_fechas:
        semanas.append([
            {
                "fecha": dia,
                "es_mes_actual": dia.month == mes,
                "es_hoy": dia == hoy,
                "eventos": actividades_por_dia[dia],
            }
            for dia in semana
        ])

    primer_dia_mes = date(anio, mes, 1)
    mes_anterior = primer_dia_mes - timedelta(days=1)

    mes_siguiente = (
        primer_dia_mes
        + timedelta(days=calendar.monthrange(anio, mes)[1])
    )

    filtros = {
        "deporte": deporte,
        "ubicacion": ubicacion,
        "tipo": tipo,
    }

    def consulta_para(fecha):
        return urlencode({
            **filtros,
            "anio": fecha.year,
            "mes": fecha.month,
        })

    consulta_anterior = None
    consulta_siguiente = None

    if mes_anterior.year >= 1901:
        consulta_anterior = consulta_para(mes_anterior)

    if mes_siguiente.year <= 2099:
        consulta_siguiente = consulta_para(mes_siguiente)

    contexto = {
        "semanas": semanas,
        "dias_semana": (
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        ),
        "mes": mes,
        "anio": anio,
        "nombre_mes": MESES[mes],
        "meses": [
            (numero, MESES[numero])
            for numero in range(1, 13)
        ],
        "tipos": Actividad.Tipo.choices,
        "filtros": filtros,
        "consulta_anterior": consulta_anterior,
        "consulta_siguiente": consulta_siguiente,
        "consulta_hoy": consulta_para(hoy),
        "consulta_limpiar": urlencode({
            "anio": anio,
            "mes": mes,
        }),
        "total_actividades": len(actividades),
    }

    return render(
        request,
        "actividades/calendario_publico.html",
        contexto,
    )


@require_safe
def detalle_publico(request, actividad_id):
    actividad = get_object_or_404(
        actividades_publicas(),
        pk=actividad_id,
    )

    inicio_local = timezone.localtime(actividad.fecha_inicio)

    consulta_calendario = urlencode({
        "anio": inicio_local.year,
        "mes": inicio_local.month,
    })

    return render(
        request,
        "actividades/detalle_publico.html",
        {
            "actividad": actividad,
            "consulta_calendario": consulta_calendario,
        },
    )