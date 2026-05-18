"""
Perseus v4 — views/rrhh.py
Panel RRHH, gestión de ausencias, vacaciones, turnos, nómina.
"""
import logging
import openpyxl
import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from datetime import timedelta

from apps.asistencia.models import (
    Marcacion, SolicitudMarca, Vacacion, LicenciaMedica,
    DiaAdministrativo, Feriado, Perfil, Empresa, Turno, AsignacionTurno
)
from apps.asistencia.forms import VacacionForm, LicenciaForm
from .mixins import (
    requiere_perfil, requiere_empresa,
    requiere_empleador, requiere_superadmin
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# PANEL RRHH
# ══════════════════════════════════════════════════════════════

@login_required
@requiere_empleador
def panel_rrhh(request):
    """Panel central de RRHH con solicitudes, estado de trabajadores y ausencias."""
    hoy = timezone.localdate()
    from django.db.models import F
    solicitudes = (
        SolicitudMarca.objects
        .filter(estado='PENDIENTE', trabajador=F('solicitante'))
        .select_related('trabajador', 'trabajador__perfil')
        .order_by('creado_en')
    )

    vacaciones_pendientes = (
        Vacacion.objects
        .filter(estado='PENDIENTE')
        .select_related('trabajador', 'trabajador__perfil')
        .order_by('inicio')
    )

    dias_admin_pendientes = (
        DiaAdministrativo.objects
        .filter(estado='PENDIENTE')
        .select_related('trabajador', 'trabajador__perfil')
        .order_by('fecha')
    )

    # Clima laboral últimos 7 días
    semana = timezone.now() - timedelta(days=7)
    data_animo = (
        Marcacion.objects
        .filter(tipo='SALIDA', timestamp__gte=semana, animo__isnull=False)
        .values('animo')
        .annotate(total=Count('animo'))
    )
    animo = {'FELIZ': 0, 'NEUTRAL': 0, 'MOLESTO': 0}
    for item in data_animo:
        if item['animo'] in animo:
            animo[item['animo']] = item['total']

    # Trabajadores activos hoy
    activos_hoy = (
        Marcacion.objects
        .filter(timestamp__date=hoy, tipo='ENTRADA')
        .values('trabajador')
        .distinct()
        .count()
    )

    # ── Estado de trabajadores HOY ──────────────────────────
    empresa = getattr(getattr(request.user, 'perfil', None), 'empresa', None)
    trabajadores_empresa = User.objects.filter(
        perfil__empresa=empresa, is_active=True, is_staff=False
    ).select_related('perfil') if empresa else User.objects.none()

    # Quiénes marcaron entrada hoy
    con_marca_hoy = set(
        Marcacion.objects
        .filter(timestamp__date=hoy, tipo='ENTRADA')
        .values_list('trabajador_id', flat=True)
    )

    # Quiénes están de vacaciones aprobadas hoy
    de_vacaciones = set(
        Vacacion.objects
        .filter(estado='APROBADA', inicio__lte=hoy, fin__gte=hoy)
        .values_list('trabajador_id', flat=True)
    )

    # Quiénes tienen licencia hoy
    con_licencia = set(
        LicenciaMedica.objects
        .filter(inicio__lte=hoy, fin__gte=hoy)
        .values_list('trabajador_id', flat=True)
    )

    # Quiénes tienen día admin aprobado hoy
    con_dia_admin = set(
        DiaAdministrativo.objects
        .filter(estado='APROBADO', fecha=hoy)
        .values_list('trabajador_id', flat=True)
    )

    es_feriado = Feriado.objects.filter(fecha=hoy).first()

    # Clasificar cada trabajador
    estado_trabajadores = []
    for t in trabajadores_empresa:
        p = getattr(t, 'perfil', None)
        if not p or not p.debe_trabajar_hoy():
            continue
        if t.id in de_vacaciones:
            estado = 'vacacion'
        elif t.id in con_licencia:
            estado = 'licencia'
        elif t.id in con_dia_admin:
            estado = 'dia_admin'
        elif es_feriado:
            estado = 'feriado'
        elif t.id in con_marca_hoy:
            estado = 'presente'
        else:
            estado = 'ausente'

        estado_trabajadores.append({
            'trabajador': t,
            'estado':     estado,
        })

    # Conteos para KPIs
    conteo_estados = {
        'presente':  sum(1 for e in estado_trabajadores if e['estado'] == 'presente'),
        'ausente':   sum(1 for e in estado_trabajadores if e['estado'] == 'ausente'),
        'vacacion':  sum(1 for e in estado_trabajadores if e['estado'] == 'vacacion'),
        'licencia':  sum(1 for e in estado_trabajadores if e['estado'] == 'licencia'),
        'dia_admin': sum(1 for e in estado_trabajadores if e['estado'] == 'dia_admin'),
    }

    ctx = {
        'solicitudes':           solicitudes,
        'vacaciones_pendientes': vacaciones_pendientes,
        'dias_admin_pendientes': dias_admin_pendientes,
        'grafico_feliz':         animo['FELIZ'],
        'grafico_neutral':       animo['NEUTRAL'],
        'grafico_molesto':       animo['MOLESTO'],
        'total_pendientes':      solicitudes.count() + vacaciones_pendientes.count() + dias_admin_pendientes.count(),
        'trabajadores_activos':  activos_hoy,
        'estado_trabajadores':   estado_trabajadores,
        'conteo_estados':        conteo_estados,
        'es_feriado':            es_feriado,
        'hoy':                   hoy,
    }
    return render(request, 'asistencia/panel_rrhh.html', ctx)


# ══════════════════════════════════════════════════════════════
# PANEL EMPRESA
# ══════════════════════════════════════════════════════════════

@login_required
@requiere_empleador
@requiere_empresa
def panel_empresa(request):
    """Vista de todas las marcaciones de la empresa con filtros."""
    empresa = request.empresa

    marcas = (
        Marcacion.objects
        .filter(empresa=empresa)
        .select_related('trabajador', 'trabajador__perfil')
        .order_by('-timestamp')
    )

    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin    = request.GET.get('fecha_fin')
    busqueda     = request.GET.get('busqueda', '').strip()

    if fecha_inicio and fecha_fin:
        marcas = marcas.filter(timestamp__date__range=[fecha_inicio, fecha_fin])

    if busqueda:
        marcas = marcas.filter(
            Q(trabajador__first_name__icontains=busqueda) |
            Q(trabajador__last_name__icontains=busqueda)  |
            Q(trabajador__perfil__rut__icontains=busqueda)
        )

    paginator = Paginator(marcas, 50)
    page_obj  = paginator.get_page(request.GET.get('page'))

    ctx = {
        'page_obj':     page_obj,
        'marcas':       page_obj.object_list,
        'empresa':      empresa,
        'fecha_inicio': fecha_inicio or '',
        'fecha_fin':    fecha_fin or '',
        'busqueda':     busqueda,
    }
    return render(request, 'asistencia/panel_empresa.html', ctx)


# ══════════════════════════════════════════════════════════════
# SOLICITUDES DE MARCA
# ══════════════════════════════════════════════════════════════

@login_required
def crear_solicitud_trabajador(request):
    """El trabajador solicita corrección o nueva marca."""
    if request.method != 'POST':
        return redirect('dashboard')

    tipo_sol   = request.POST.get('tipo_solicitud')
    fecha_str  = request.POST.get('fecha')
    hora_str   = request.POST.get('hora')
    motivo     = request.POST.get('motivo', '').strip()
    tipo_marca = request.POST.get('tipo_marca')
    marca_id   = request.POST.get('marca_id')

    if not motivo:
        messages.error(request, 'El motivo es obligatorio.')
        return redirect('dashboard')

    try:
        fh_naive = datetime.datetime.strptime(f'{fecha_str} {hora_str}', '%Y-%m-%d %H:%M')
        fh_aware = timezone.make_aware(fh_naive)
    except (ValueError, TypeError):
        messages.error(request, 'Fecha u hora inválida.')
        return redirect('dashboard')

    sol = SolicitudMarca(
        trabajador           = request.user,
        solicitante          = request.user,
        tipo_solicitud       = tipo_sol,
        fecha_hora_propuesta = fh_aware,
        motivo               = motivo,
        estado               = 'PENDIENTE',
    )

    if tipo_sol == 'RECTIFICACION' and marca_id:
        try:
            orig = Marcacion.objects.get(id=marca_id, trabajador=request.user)
            sol.marca_original       = orig
            sol.tipo_marca_propuesta = orig.tipo
        except Marcacion.DoesNotExist:
            messages.error(request, 'Marca no encontrada.')
            return redirect('dashboard')
    else:
        sol.tipo_marca_propuesta = tipo_marca or 'ENTRADA'

    sol.save()
    messages.success(request, 'Solicitud enviada a RRHH.')
    return redirect('dashboard')


@login_required
@requiere_empleador
def responder_solicitud(request, sol_id, accion):
    """RRHH acepta o rechaza una solicitud de corrección."""
    sol      = get_object_or_404(SolicitudMarca, id=sol_id)
    es_dueno = sol.trabajador == request.user
    es_jefe  = request.user.is_staff or request.user.is_superuser

    if not (es_dueno or es_jefe):
        messages.error(request, 'Sin permiso para gestionar esta solicitud.')
        return redirect('dashboard')

    if sol.estado != 'PENDIENTE':
        messages.warning(request, 'Esta solicitud ya fue procesada.')
        return redirect('panel_rrhh')

    if accion == 'RECHAZAR':
        sol.estado = 'RECHAZADA'
        sol.save()
        messages.warning(request, 'Solicitud rechazada.')

    elif accion == 'ACEPTAR':
        try:
            with transaction.atomic():
                if sol.tipo_solicitud == 'NUEVA':
                    Marcacion.objects.create(
                        trabajador   = sol.trabajador,
                        timestamp    = sol.fecha_hora_propuesta,
                        tipo         = sol.tipo_marca_propuesta,
                        es_manual    = True,
                        observacion  = f'Aprobada por RRHH. Motivo: {sol.motivo}',
                    )
                elif sol.tipo_solicitud == 'RECTIFICACION' and sol.marca_original:
                    sol.marca_original.estado = 'RECTIFICADA'
                    sol.marca_original.save(update_fields=['estado'])
                    Marcacion.objects.create(
                        trabajador        = sol.trabajador,
                        timestamp         = sol.fecha_hora_propuesta,
                        tipo              = sol.tipo_marca_propuesta,
                        es_manual         = True,
                        marca_reemplazada = sol.marca_original,
                        observacion       = f'Rectificación. Motivo: {sol.motivo}',
                    )
                sol.estado = 'ACEPTADA'
                sol.save()
                messages.success(request, 'Solicitud aceptada y procesada.')
        except Exception as e:
            messages.error(request, f'Error al procesar: {e}')

    return redirect('panel_rrhh')


# ══════════════════════════════════════════════════════════════
# VACACIONES
# ══════════════════════════════════════════════════════════════

@login_required
def mis_vacaciones(request):
    if request.method == 'POST':
        fi = request.POST.get('fecha_inicio')
        ff = request.POST.get('fecha_fin')
        if fi and ff:
            v = Vacacion(
                trabajador = request.user,
                inicio     = fi,
                fin        = ff,
                comentario = request.POST.get('motivo', ''),
                estado     = 'PENDIENTE',
            )
            v.save()
            messages.success(request, f'Solicitud enviada a RRHH ({v.dias_habiles} días hábiles).')
            return redirect('mis_vacaciones')

    solicitudes = Vacacion.objects.filter(
        trabajador=request.user
    ).order_by('-inicio')

    # ── Cálculo real de saldo de vacaciones ──────────────────
    # Base legal Chile: 15 días hábiles por año trabajado (Art. 67 CT)
    DIAS_BASE = 15

    # Días ya consumidos en vacaciones APROBADAS del año en curso
    from django.utils import timezone as tz
    anio_actual = tz.localdate().year
    dias_usados = sum(
        v.dias_habiles
        for v in solicitudes
        if v.estado == 'APROBADA' and v.inicio.year == anio_actual
    )

    # Días en solicitudes PENDIENTES (reservados pero aún no confirmados)
    dias_pendientes = sum(
        v.dias_habiles
        for v in solicitudes
        if v.estado == 'PENDIENTE' and v.inicio.year == anio_actual
    )

    dias_disponibles = max(0, DIAS_BASE - dias_usados)

    ctx = {
        'solicitudes':     solicitudes,
        'dias_disponibles':dias_disponibles,
        'dias_usados':     dias_usados,
        'dias_pendientes': dias_pendientes,
        'dias_base':       DIAS_BASE,
    }
    return render(request, 'asistencia/mis_vacaciones.html', ctx)


@login_required
@requiere_empleador
def gestionar_ausencias(request):
    hoy       = timezone.localdate()
    form_vac  = VacacionForm(request.POST or None)
    form_lic  = LicenciaForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if 'btn_vacacion' in request.POST and form_vac.is_valid():
            form_vac.save()
            messages.success(request, 'Vacaciones registradas.')
            return redirect('gestionar_ausencias')
        elif 'btn_licencia' in request.POST and form_lic.is_valid():
            form_lic.save()
            messages.success(request, 'Licencia registrada.')
            return redirect('gestionar_ausencias')

    ctx = {
        'vacaciones':   Vacacion.objects.all().select_related('trabajador').order_by('-inicio'),
        'licencias':    LicenciaMedica.objects.all().select_related('trabajador').order_by('-inicio'),
        'form_vacacion':form_vac,
        'form_licencia':form_lic,
        'hoy':          hoy,
    }
    return render(request, 'asistencia/gestionar_ausencias.html', ctx)


@login_required
@requiere_empleador
def aprobar_vacacion(request, vac_id, estado):
    v = get_object_or_404(Vacacion, id=vac_id)
    if estado in ('APROBADA', 'RECHAZADA'):
        v.estado      = estado
        v.aprobado_por= request.user
        v.save(update_fields=['estado', 'aprobado_por'])
        messages.success(request, f'Vacación {estado.lower()}.')
    return redirect('gestionar_ausencias')


# ══════════════════════════════════════════════════════════════
# DÍAS ADMINISTRATIVOS
# ══════════════════════════════════════════════════════════════

@login_required
def mis_dias_admin(request):
    if request.method == 'POST':
        DiaAdministrativo.objects.create(
            trabajador   = request.user,
            fecha        = request.POST.get('fecha'),
            tipo_jornada = request.POST.get('tipo_jornada', 'COMPLETO'),
            motivo       = request.POST.get('motivo', ''),
        )
        messages.success(request, 'Solicitud enviada a RRHH.')
        return redirect('mis_dias_admin')

    ctx = {
        'solicitudes': DiaAdministrativo.objects.filter(trabajador=request.user).order_by('-fecha')
    }
    return render(request, 'asistencia/mis_dias_admin.html', ctx)


@login_required
@requiere_empleador
def gestionar_dia_admin(request, sol_id, accion):
    sol = get_object_or_404(DiaAdministrativo, id=sol_id)
    if accion == 'aprobar':
        sol.estado = 'APROBADO'
        messages.success(request, f'Solicitud de {sol.trabajador.first_name} aprobada.')
    elif accion == 'rechazar':
        sol.estado = 'RECHAZADO'
        messages.error(request, f'Solicitud de {sol.trabajador.first_name} rechazada.')
    sol.save(update_fields=['estado'])
    return redirect('panel_rrhh')


# ══════════════════════════════════════════════════════════════
# TURNOS
# ══════════════════════════════════════════════════════════════

@login_required
@requiere_empleador
@requiere_empresa
def turnos(request):
    """Gestión de turnos de la empresa."""
    empresa = request.empresa

    if request.method == 'POST':
        accion = request.POST.get('accion', 'crear')

        # ── Crear turno ───────────────────────────────────────
        if accion == 'crear':
            nombre      = request.POST.get('nombre', '').strip()
            hora_inicio = request.POST.get('hora_inicio')
            hora_fin    = request.POST.get('hora_fin')
            color       = request.POST.get('color', '#1a6644')

            if not nombre or not hora_inicio or not hora_fin:
                messages.error(request, 'Nombre, hora inicio y hora fin son obligatorios.')
            elif Turno.objects.filter(empresa=empresa, nombre=nombre).exists():
                messages.error(request, f'Ya existe un turno llamado "{nombre}" en esta empresa.')
            else:
                Turno.objects.create(
                    empresa     = empresa,
                    nombre      = nombre,
                    hora_inicio = hora_inicio,
                    hora_fin    = hora_fin,
                    color       = color,
                    activo      = True,
                )
                messages.success(request, f'Turno "{nombre}" creado correctamente.')

        # ── Desactivar turno ──────────────────────────────────
        elif accion == 'desactivar':
            turno_id = request.POST.get('turno_id')
            try:
                t = Turno.objects.get(id=turno_id, empresa=empresa)
                t.activo = False
                t.save(update_fields=['activo'])
                messages.success(request, f'Turno "{t.nombre}" desactivado.')
            except Turno.DoesNotExist:
                messages.error(request, 'Turno no encontrado.')

        # ── Reactivar turno ───────────────────────────────────
        elif accion == 'reactivar':
            turno_id = request.POST.get('turno_id')
            try:
                t = Turno.objects.get(id=turno_id, empresa=empresa)
                t.activo = True
                t.save(update_fields=['activo'])
                messages.success(request, f'Turno "{t.nombre}" reactivado.')
            except Turno.DoesNotExist:
                messages.error(request, 'Turno no encontrado.')

        return redirect('turnos')

    # GET
    turnos_activos   = Turno.objects.filter(empresa=empresa, activo=True).order_by('hora_inicio')
    turnos_inactivos = Turno.objects.filter(empresa=empresa, activo=False).order_by('nombre')

    colores = [
        ('#1a6644', 'Verde'),
        ('#185fa5', 'Azul'),
        ('#7a4a00', 'Ámbar'),
        ('#991f1f', 'Rojo'),
        ('#534ab7', 'Morado'),
        ('#1a1a1a', 'Negro'),
    ]

    ctx = {
        'turnos':          turnos_activos,
        'turnos_inactivos':turnos_inactivos,
        'empresa':         empresa,
        'colores':         colores,
    }
    return render(request, 'asistencia/turnos.html', ctx)


# ══════════════════════════════════════════════════════════════
# IMPORTAR NÓMINA
# ══════════════════════════════════════════════════════════════

@login_required
@requiere_superadmin
def importar_nomina(request):
    """Carga masiva de trabajadores desde Excel."""
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        excel_file = request.FILES['archivo_excel']
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            creados = actualizados = 0

            with transaction.atomic():
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or not row[0]:
                        continue

                    username   = str(row[0]).strip()
                    email      = str(row[1]).strip() if row[1] else ''
                    first_name = str(row[2]).strip() if row[2] else ''
                    last_name  = str(row[3]).strip() if row[3] else ''
                    rut        = str(row[4]).strip() if row[4] else ''
                    cargo      = str(row[5]).strip() if row[5] else ''

                    user, created = User.objects.get_or_create(username=username)
                    user.email = email
                    user.first_name = first_name
                    user.last_name  = last_name
                    if created:
                        pwd = rut.replace('.', '').replace('-', '') or '123456'
                        user.set_password(pwd)
                        creados += 1
                    else:
                        actualizados += 1
                    user.save()

                    perfil, _ = Perfil.objects.get_or_create(usuario=user)
                    perfil.rut   = rut
                    perfil.cargo = cargo
                    if request.empresa:
                        perfil.empresa = request.empresa
                    perfil.cambiar_pass = True
                    perfil.save()

            messages.success(
                request,
                f'Proceso completado: {creados} nuevos · {actualizados} actualizados.'
            )
        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {e}')
            logger.error(f"importar_nomina error: {e}")

    return render(request, 'asistencia/importar_nomina.html')


# ══════════════════════════════════════════════════════════════
# CARGAR FERIADOS
# ══════════════════════════════════════════════════════════════

@login_required
@requiere_superadmin
def cargar_feriados(request):
    """Carga feriados de Chile desde un archivo Excel o manualmente."""
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        desc      = request.POST.get('descripcion', '').strip()
        if fecha_str and desc:
            Feriado.objects.get_or_create(
                fecha=fecha_str,
                defaults={'descripcion': desc}
            )
            messages.success(request, f'Feriado "{desc}" agregado.')
            return redirect('cargar_feriados')

    feriados = Feriado.objects.order_by('fecha')
    ctx = {'feriados': feriados}
    return render(request, 'asistencia/feriados.html', ctx)