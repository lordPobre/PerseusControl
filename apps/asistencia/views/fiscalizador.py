"""Perseus v4 — views/fiscalizador.py"""
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from apps.asistencia.models import Marcacion
from .mixins import requiere_fiscalizador, requiere_empresa

logger = logging.getLogger(__name__)


@login_required
@requiere_fiscalizador
@requiere_empresa
def panel_fiscalizador(request):
    empresa = request.empresa
    desde   = request.GET.get('desde')
    hasta   = request.GET.get('hasta')

    marcas_qs = (
        Marcacion.objects
        .filter(empresa=empresa)
        .select_related('trabajador', 'trabajador__perfil')
        .order_by('trabajador', 'timestamp')
    )

    if desde and hasta:
        marcas_qs = marcas_qs.filter(timestamp__range=[desde, hasta + ' 23:59:59'])
    else:
        marcas_qs = marcas_qs.filter(timestamp__gte=timezone.now() - timedelta(days=30))

    # Algoritmo de emparejamiento entrada–salida
    jornadas, entrada_pend = [], None

    for marca in marcas_qs:
        if entrada_pend and entrada_pend.trabajador != marca.trabajador:
            jornadas.append({'trabajador': entrada_pend.trabajador,
                             'fecha': entrada_pend.timestamp,
                             'entrada': entrada_pend.timestamp,
                             'salida': None,
                             'duracion': 'Sin salida', 'estado': 'warning'})
            entrada_pend = None

        if marca.tipo == 'ENTRADA':
            if entrada_pend:
                jornadas.append({'trabajador': entrada_pend.trabajador,
                                 'fecha': entrada_pend.timestamp,
                                 'entrada': entrada_pend.timestamp,
                                 'salida': None,
                                 'duracion': 'Doble entrada', 'estado': 'warning'})
            entrada_pend = marca

        elif marca.tipo == 'SALIDA':
            if entrada_pend:
                diff = marca.timestamp - entrada_pend.timestamp
                s    = int(diff.total_seconds())
                jornadas.append({'trabajador': marca.trabajador,
                                 'fecha': marca.timestamp,
                                 'entrada': entrada_pend.timestamp,
                                 'salida': marca.timestamp,
                                 'duracion': f"{s//3600}h {(s%3600)//60}m",
                                 'estado': 'success'})
                entrada_pend = None
            else:
                jornadas.append({'trabajador': marca.trabajador,
                                 'fecha': marca.timestamp,
                                 'entrada': None, 'salida': marca.timestamp,
                                 'duracion': 'Sin entrada', 'estado': 'danger'})

    if entrada_pend:
        jornadas.append({'trabajador': entrada_pend.trabajador,
                         'fecha': entrada_pend.timestamp,
                         'entrada': entrada_pend.timestamp,
                         'salida': None, 'duracion': 'En curso', 'estado': 'info'})

    jornadas.reverse()

    ctx = {'empresa': empresa, 'jornadas': jornadas, 'desde': desde, 'hasta': hasta}
    return render(request, 'asistencia/panel_fiscalizador.html', ctx)
