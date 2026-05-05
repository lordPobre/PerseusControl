"""
Perseus v4 — views/dashboard.py
Dashboard principal del trabajador con lógica de vacaciones,
licencias y días administrativos.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import timedelta

from apps.asistencia.models import (
    Marcacion, SolicitudMarca, Vacacion,
    LicenciaMedica, DiaAdministrativo, Feriado
)
from .mixins import requiere_perfil

logger = logging.getLogger(__name__)


def _estado_ausencia_hoy(user, hoy):
    """
    Retorna dict con estado de ausencia justificada del trabajador hoy.
    Orden de prioridad: Vacación > Licencia > Día Admin > Feriado
    """
    vacacion = Vacacion.objects.filter(
        trabajador=user, estado='APROBADA',
        inicio__lte=hoy, fin__gte=hoy,
    ).first()
    if vacacion:
        return {
            'tipo':    'VACACION',
            'label':   'De vacaciones',
            'detalle': f'Del {vacacion.inicio.strftime("%d/%m")} al {vacacion.fin.strftime("%d/%m/%Y")} · {vacacion.dias_habiles} días hábiles',
            'color':   'g',
            'icono':   '🏖️',
        }

    licencia = LicenciaMedica.objects.filter(
        trabajador=user,
        inicio__lte=hoy, fin__gte=hoy,
    ).first()
    if licencia:
        return {
            'tipo':    'LICENCIA',
            'label':   'Con licencia médica',
            'detalle': f'{licencia.get_tipo_display()} · hasta {licencia.fin.strftime("%d/%m/%Y")}',
            'color':   'b',
            'icono':   '🏥',
        }

    dia_admin = DiaAdministrativo.objects.filter(
        trabajador=user, estado='APROBADO', fecha=hoy,
    ).first()
    if dia_admin:
        return {
            'tipo':    'DIA_ADMIN',
            'label':   'Día administrativo',
            'detalle': dia_admin.get_tipo_jornada_display(),
            'color':   'a',
            'icono':   '📋',
        }

    feriado = Feriado.objects.filter(fecha=hoy).first()
    if feriado:
        return {
            'tipo':    'FERIADO',
            'label':   'Feriado',
            'detalle': feriado.descripcion,
            'color':   'pu',
            'icono':   '🎉',
        }

    return None


@login_required
@requiere_perfil
def dashboard(request):
    perfil = request.user.perfil
    if perfil.cambiar_pass:
        return redirect('cambiar_password')

    hoy   = timezone.localdate()
    ahora = timezone.now()

    marcas_hoy = (
        Marcacion.objects
        .filter(trabajador=request.user, timestamp__date=hoy)
        .order_by('timestamp')
    )
    ultima_marca = marcas_hoy.last()

    solicitudes_pendientes = (
        SolicitudMarca.objects
        .filter(trabajador=request.user, estado='PENDIENTE')
        .exclude(solicitante=request.user)
        .select_related('solicitante')
    )

    minutos_hoy = 0
    primera_entrada = marcas_hoy.filter(tipo='ENTRADA').first()
    if primera_entrada:
        diff = ahora - primera_entrada.timestamp
        minutos_hoy = max(0, int(diff.total_seconds() // 60))

    semana_inicio = ahora - timedelta(days=7)
    data_animo = (
        Marcacion.objects
        .filter(
            trabajador=request.user, tipo='SALIDA',
            timestamp__gte=semana_inicio, animo__isnull=False,
        )
        .values('animo').annotate(total=Count('animo'))
    )
    animo = {'FELIZ': 0, 'NEUTRAL': 0, 'MOLESTO': 0}
    for item in data_animo:
        if item['animo'] in animo:
            animo[item['animo']] = item['total']

    vacaciones_pendientes = Vacacion.objects.filter(
        trabajador=request.user, estado='PENDIENTE'
    ).count()

    ausencia_hoy = _estado_ausencia_hoy(request.user, hoy)

    ctx = {
        'marcas_hoy':             marcas_hoy,
        'ultima_marca':           ultima_marca,
        'solicitudes_pendientes': solicitudes_pendientes,
        'minutos_hoy':            minutos_hoy,
        'hoy':                    hoy,
        'mi_feliz':               animo['FELIZ'],
        'mi_neutral':             animo['NEUTRAL'],
        'mi_molesto':             animo['MOLESTO'],
        'vacaciones_pendientes':  vacaciones_pendientes,
        'ausencia_hoy':           ausencia_hoy,
    }
    return render(request, 'asistencia/dashboard.html', ctx)


@login_required
def mis_marcas(request):
    from django.core.paginator import Paginator
    qs = Marcacion.objects.filter(trabajador=request.user).order_by('-timestamp')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin    = request.GET.get('fecha_fin')
    if fecha_inicio and fecha_fin:
        qs = qs.filter(timestamp__date__range=[fecha_inicio, fecha_fin])
    paginator = Paginator(qs, 30)
    page_obj  = paginator.get_page(request.GET.get('page'))
    ctx = {
        'page_obj':     page_obj,
        'marcas':       page_obj.object_list,
        'fecha_inicio': fecha_inicio or '',
        'fecha_fin':    fecha_fin or '',
    }
    return render(request, 'asistencia/mis_marcas.html', ctx)


@login_required
def privacidad(request):
    return render(request, 'asistencia/privacidad.html')

@login_required
def ayuda(request):
    return render(request, 'asistencia/ayuda.html')