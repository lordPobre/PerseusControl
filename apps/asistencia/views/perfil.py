"""
Perseus v4 — views/perfil.py
Perfil editable del trabajador: datos personales y cambio de contraseña.
"""
import logging
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.asistencia.models import Marcacion, Vacacion, LicenciaMedica

logger = logging.getLogger(__name__)


@login_required
def perfil(request):
    """Vista de perfil editable del trabajador."""
    user   = request.user
    perfil = getattr(user, 'perfil', None)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'datos':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name  = request.POST.get('last_name', '').strip()
            user.email      = request.POST.get('email', '').strip()
            user.save(update_fields=['first_name', 'last_name', 'email'])
            if perfil and hasattr(perfil, 'telefono'):
                perfil.telefono = request.POST.get('telefono', '').strip()
                perfil.save(update_fields=['telefono'])
            messages.success(request, 'Datos actualizados correctamente.')
            return redirect('mi_perfil')

        elif accion == 'password':
            actual    = request.POST.get('password_actual', '')
            nueva     = request.POST.get('password_nueva', '')
            confirmar = request.POST.get('password_confirmar', '')
            if not user.check_password(actual):
                messages.error(request, 'La contraseña actual es incorrecta.')
                return redirect('mi_perfil')
            if len(nueva) < 8:
                messages.error(request, 'La nueva contraseña debe tener al menos 8 caracteres.')
                return redirect('mi_perfil')
            if nueva != confirmar:
                messages.error(request, 'Las contraseñas nuevas no coinciden.')
                return redirect('mi_perfil')
            user.set_password(nueva)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Contraseña cambiada correctamente.')
            return redirect('mi_perfil')

    # ── GET — estadísticas ───────────────────────────────────
    hoy        = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    anio       = hoy.year

    # Marcas del mes
    marcas_mes = Marcacion.objects.filter(
        trabajador=user,
        timestamp__date__gte=inicio_mes,
    )
    dias_trabajados = (
        marcas_mes
        .filter(tipo='ENTRADA')
        .values('timestamp__date')
        .distinct()
        .count()
    )

    # ── Vacaciones reales ────────────────────────────────────
    DIAS_BASE = 15
    vacaciones_anio = Vacacion.objects.filter(
        trabajador=user,
        inicio__year=anio,
    )
    dias_usados = sum(
        v.dias_habiles for v in vacaciones_anio
        if v.estado == 'APROBADA'
    )
    dias_pendientes = sum(
        v.dias_habiles for v in vacaciones_anio
        if v.estado == 'PENDIENTE'
    )
    dias_disponibles = max(0, DIAS_BASE - dias_usados)

    # ── Licencias activas ────────────────────────────────────
    licencias_activas = LicenciaMedica.objects.filter(
        trabajador=user,
        fin__gte=hoy,
    ).order_by('inicio')

    ctx = {
        'dias_trabajados':  dias_trabajados,
        'total_marcas':     marcas_mes.count(),
        'dias_disponibles': dias_disponibles,
        'dias_usados':      dias_usados,
        'dias_pendientes':  dias_pendientes,
        'dias_base':        DIAS_BASE,
        'licencias_activas':licencias_activas,
    }
    return render(request, 'asistencia/perfil.html', ctx)