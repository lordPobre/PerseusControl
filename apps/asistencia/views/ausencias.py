
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.asistencia.models import (
    Vacacion, LicenciaMedica, DiaAdministrativo, Feriado
)

logger = logging.getLogger(__name__)


@login_required
def ausencias(request):
    """
    Vista unificada de todas las ausencias del trabajador.
    Permite solicitar vacaciones, subir licencias y pedir días admin.
    """
    user = request.user
    hoy  = timezone.localdate()

    # ── POST: detectar qué formulario se envió ────────────────
    if request.method == 'POST':
        accion = request.POST.get('accion')

        # Solicitar vacaciones
        if accion == 'vacacion':
            fi = request.POST.get('fecha_inicio')
            ff = request.POST.get('fecha_fin')
            if fi and ff:
                v = Vacacion(
                    trabajador = user,
                    inicio     = fi,
                    fin        = ff,
                    comentario = request.POST.get('motivo', ''),
                    estado     = 'PENDIENTE',
                )
                v.save()
                messages.success(
                    request,
                    f'Solicitud de vacaciones enviada a RRHH ({v.dias_habiles} días hábiles).'
                )
            return redirect('ausencias')

        # Subir licencia médica
        elif accion == 'licencia':
            inicio = request.POST.get('inicio')
            fin    = request.POST.get('fin')
            tipo   = request.POST.get('tipo', 'ENFERMEDAD')
            folio  = request.POST.get('folio', '').strip()
            doc    = request.FILES.get('documento')

            if not inicio or not fin:
                messages.error(request, 'Las fechas de la licencia son obligatorias.')
                return redirect('mis_ausencias')

            lic = LicenciaMedica(
                trabajador = user,
                inicio     = inicio,
                fin        = fin,
                tipo       = tipo,
                folio      = folio,
                estado     = 'PENDIENTE',
            )
            if doc:
                lic.documento = doc
            lic.save()
            messages.success(
                request,
                'Licencia médica enviada a RRHH para revisión.'
            )
            return redirect('ausencias')

        # Solicitar día administrativo
        elif accion == 'dia_admin':
            fecha    = request.POST.get('fecha')
            jornada  = request.POST.get('tipo_jornada', 'COMPLETO')
            motivo   = request.POST.get('motivo', '')
            if fecha:
                DiaAdministrativo.objects.create(
                    trabajador   = user,
                    fecha        = fecha,
                    tipo_jornada = jornada,
                    motivo       = motivo,
                )
                messages.success(request, 'Solicitud de día administrativo enviada a RRHH.')
            return redirect('ausencias')

    # ── GET: cargar datos ────────────────────────────────────
    anio = hoy.year

    # Vacaciones
    vacaciones = Vacacion.objects.filter(
        trabajador=user
    ).order_by('-inicio')

    dias_base       = 15
    dias_usados     = sum(v.dias_habiles for v in vacaciones if v.estado == 'APROBADA' and v.inicio.year == anio)
    dias_pendientes = sum(v.dias_habiles for v in vacaciones if v.estado == 'PENDIENTE' and v.inicio.year == anio)
    dias_disponibles= max(0, dias_base - dias_usados)

    # Licencias
    licencias = LicenciaMedica.objects.filter(
        trabajador=user
    ).order_by('-inicio')

    # Días administrativos
    dias_admin = DiaAdministrativo.objects.filter(
        trabajador=user
    ).order_by('-fecha')

    # Tab activo (GET param)
    tab_activo = request.GET.get('tab', 'vacaciones')

    ctx = {
        'vacaciones':       vacaciones,
        'licencias':        licencias,
        'dias_admin':       dias_admin,
        'dias_base':        dias_base,
        'dias_usados':      dias_usados,
        'dias_pendientes':  dias_pendientes,
        'dias_disponibles': dias_disponibles,
        'tab_activo':       tab_activo,
        'hoy':              hoy,
        'tipo_licencia_choices': LicenciaMedica.TIPO_CHOICES,
    }
    return render(request, 'asistencia/ausencias.html', ctx)


@login_required
def aprobar_licencia(request, lic_id, estado):
    """RRHH aprueba o rechaza una licencia médica."""
    from apps.asistencia.views.mixins import requiere_empleador
    from django.shortcuts import get_object_or_404

    # Verificar permisos manualmente aquí
    perfil = getattr(request.user, 'perfil', None)
    if not (request.user.is_superuser or (perfil and perfil.es_empleador())):
        messages.error(request, 'Sin permiso.')
        return redirect('dashboard')

    lic = get_object_or_404(LicenciaMedica, id=lic_id)
    if estado in ('APROBADA', 'RECHAZADA'):
        lic.estado = estado
        lic.comentario_rrhh = request.POST.get('comentario', '')
        lic.save(update_fields=['estado', 'comentario_rrhh'])
        messages.success(request, f'Licencia {estado.lower()} correctamente.')
    return redirect('gestionar_ausencias')