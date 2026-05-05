"""
Perseus v4 — apps/asistencia/tasks.py
Tareas Celery para alertas automáticas de asistencia.

Tareas definidas:
  - revisar_ausencias       → alerta si no ha marcado entrada pasada la tolerancia
  - revisar_exceso_jornada  → alerta si lleva más de jornada + 2h trabajando
  - limpiar_logs_alertas    → limpia logs de más de 30 días
"""
import logging
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# TAREA 1 — AUSENCIAS
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def revisar_ausencias(self):
    """
    Revisa si algún trabajador no ha marcado entrada
    pasada la tolerancia configurada en la empresa.
    Envía email al RRHH y guarda log para no repetir.
    """
    from apps.asistencia.models import (
        Empresa, Marcacion, LogAlerta,
        Feriado, Vacacion, LicenciaMedica
    )

    hoy   = timezone.localdate()
    ahora = timezone.localtime(timezone.now())

    # No ejecutar en feriados
    if Feriado.objects.filter(fecha=hoy).exists():
        logger.info('Feriado detectado — sin alertas de ausencia.')
        return 'feriado'

    # No ejecutar en fines de semana (sábado=5, domingo=6)
    if hoy.weekday() >= 5:
        return 'fin_de_semana'

    alertas_enviadas = 0

    for empresa in Empresa.objects.filter(activa=True):
        if not empresa.email_rrhh:
            continue

        trabajadores = User.objects.filter(
            perfil__empresa=empresa,
            is_active=True,
            is_staff=False,
        ).select_related('perfil')

        for user in trabajadores:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.debe_trabajar_hoy():
                continue

            # Justificaciones: vacaciones o licencia
            if _tiene_justificacion(user, hoy):
                continue

            hora_entrada = perfil.hora_entrada
            tolerancia   = empresa.tolerancia_atraso_min or 10

            entrada_dt  = timezone.make_aware(
                datetime.combine(hoy, hora_entrada)
            )
            limite_aviso = entrada_dt + timedelta(minutes=tolerancia + 5)

            # Solo avisar si ya pasó el límite
            if ahora < limite_aviso:
                continue

            # Verificar si ya marcó entrada hoy
            ya_marco = Marcacion.objects.filter(
                trabajador=user,
                timestamp__date=hoy,
                tipo='ENTRADA',
            ).exists()

            if ya_marco:
                continue

            # Verificar si ya se envió alerta hoy
            ya_avisado = LogAlerta.objects.filter(
                trabajador=user,
                tipo='AUSENCIA',
                fecha=hoy,
            ).exists()

            if ya_avisado:
                continue

            # ── Enviar alerta ──────────────────────────────
            try:
                _enviar_alerta_ausencia(user, perfil, empresa, hora_entrada, ahora)
                LogAlerta.objects.create(
                    trabajador=user,
                    empresa=empresa,
                    tipo='AUSENCIA',
                    fecha=hoy,
                )
                alertas_enviadas += 1
                logger.info(f'Alerta ausencia enviada: {user.username} — {empresa.nombre}')
            except Exception as e:
                logger.error(f'Error enviando alerta ausencia a {user.username}: {e}')

    return f'{alertas_enviadas} alertas de ausencia enviadas'


# ══════════════════════════════════════════════════════════════
# TAREA 2 — EXCESO DE JORNADA
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def revisar_exceso_jornada(self):
    """
    Revisa si algún trabajador lleva más de su jornada + 2h
    sin registrar salida. Alerta por fatiga laboral.
    """
    from apps.asistencia.models import (
        Empresa, Marcacion, LogAlerta,
        Vacacion, LicenciaMedica
    )

    hoy   = timezone.localdate()
    ahora = timezone.localtime(timezone.now())

    alertas_enviadas = 0

    for empresa in Empresa.objects.filter(activa=True):
        if not empresa.email_rrhh:
            continue

        trabajadores = User.objects.filter(
            perfil__empresa=empresa,
            is_active=True,
            is_staff=False,
        ).select_related('perfil')

        for user in trabajadores:
            perfil = getattr(user, 'perfil', None)
            if not perfil:
                continue

            if _tiene_justificacion(user, hoy):
                continue

            # Ver última marca del día
            ultima = (
                Marcacion.objects
                .filter(trabajador=user, timestamp__date=hoy)
                .order_by('-timestamp')
                .first()
            )

            # Solo alertar si sigue "dentro" (ENTRADA o FIN_COLACION)
            if not ultima or ultima.tipo not in ('ENTRADA', 'FIN_COLACION'):
                continue

            # Calcular horas desde la primera entrada
            primera_entrada = (
                Marcacion.objects
                .filter(trabajador=user, timestamp__date=hoy, tipo='ENTRADA')
                .order_by('timestamp')
                .first()
            )

            if not primera_entrada:
                continue

            horas_trabajadas = (ahora - primera_entrada.timestamp).total_seconds() / 3600
            limite_fatiga    = (perfil.jornada_diaria or 9) + 2

            if horas_trabajadas <= limite_fatiga:
                continue

            # Verificar log para no repetir
            ya_avisado = LogAlerta.objects.filter(
                trabajador=user,
                tipo='EXCESO_HORAS',
                fecha=hoy,
            ).exists()

            if ya_avisado:
                continue

            # ── Enviar alerta ──────────────────────────────
            try:
                _enviar_alerta_exceso(user, perfil, empresa, horas_trabajadas, ahora)
                LogAlerta.objects.create(
                    trabajador=user,
                    empresa=empresa,
                    tipo='EXCESO_HORAS',
                    fecha=hoy,
                )
                alertas_enviadas += 1
                logger.info(f'Alerta exceso enviada: {user.username} — {int(horas_trabajadas)}h')
            except Exception as e:
                logger.error(f'Error enviando alerta exceso a {user.username}: {e}')

    return f'{alertas_enviadas} alertas de exceso enviadas'


# ══════════════════════════════════════════════════════════════
# TAREA 3 — LIMPIEZA DE LOGS
# ══════════════════════════════════════════════════════════════

@shared_task
def limpiar_logs_alertas():
    """Elimina logs de alertas de más de 30 días."""
    from apps.asistencia.models import LogAlerta
    hace_30_dias = timezone.now() - timedelta(days=30)
    eliminados, _ = LogAlerta.objects.filter(enviado_en__lt=hace_30_dias).delete()
    logger.info(f'Logs limpiados: {eliminados} registros eliminados')
    return f'{eliminados} logs eliminados'


# ══════════════════════════════════════════════════════════════
# HELPERS PRIVADOS
# ══════════════════════════════════════════════════════════════

def _tiene_justificacion(user, hoy):
    """Retorna True si el trabajador tiene vacación o licencia activa hoy."""
    from apps.asistencia.models import Vacacion, LicenciaMedica, DiaAdministrativo
    return (
        Vacacion.objects.filter(
            trabajador=user, estado='APROBADA',
            inicio__lte=hoy, fin__gte=hoy
        ).exists()
        or
        LicenciaMedica.objects.filter(
            trabajador=user, estado='APROBADA',
            inicio__lte=hoy, fin__gte=hoy
        ).exists()
        or
        DiaAdministrativo.objects.filter(
            trabajador=user, estado='APROBADO',
            fecha=hoy
        ).exists()
    )


def _enviar_alerta_ausencia(user, perfil, empresa, hora_entrada, ahora):
    """Envía email HTML de alerta de ausencia al RRHH."""
    asunto = f'⚠️ Ausencia sin justificar — {user.get_full_name()}'
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
      body{{font-family:system-ui,sans-serif;background:#f7f7f5;padding:20px}}
      .card{{background:#fff;border-radius:12px;max-width:520px;margin:0 auto;
        border:1px solid #e0e0e0;overflow:hidden}}
      .head{{background:#991f1f;color:#fff;padding:16px 24px}}
      .head h2{{margin:0;font-size:16px;font-weight:500}}
      .body{{padding:20px 24px}}
      .row{{display:flex;justify-content:space-between;padding:8px 0;
        border-bottom:1px solid #f0f0f0;font-size:13px}}
      .lbl{{color:#888}}.val{{font-weight:500}}
      .foot{{background:#f7f7f5;padding:12px 24px;font-size:11px;color:#999;text-align:center}}
    </style></head>
    <body><div class="card">
      <div class="head"><h2>⚠️ Alerta de Ausencia</h2><p style="margin:4px 0 0;opacity:.7;font-size:12px">{empresa.nombre}</p></div>
      <div class="body">
        <p style="font-size:13px;margin-bottom:16px">El siguiente trabajador <strong>no ha registrado entrada</strong>:</p>
        <div class="row"><span class="lbl">Trabajador</span><span class="val">{user.get_full_name()}</span></div>
        <div class="row"><span class="lbl">RUT</span><span class="val">{perfil.rut or 'S/I'}</span></div>
        <div class="row"><span class="lbl">Cargo</span><span class="val">{perfil.cargo or 'S/I'}</span></div>
        <div class="row"><span class="lbl">Hora pactada</span><span class="val">{hora_entrada.strftime('%H:%M')}</span></div>
        <div class="row"><span class="lbl">Hora de revisión</span><span class="val">{ahora.strftime('%H:%M')}</span></div>
        <div class="row"><span class="lbl">Estado</span><span class="val" style="color:#991f1f">Sin registro de entrada</span></div>
      </div>
      <div class="foot">Alerta automática · Perseus Control · {empresa.nombre}</div>
    </div></body></html>
    """
    send_mail(
        subject       = asunto,
        message       = f'Ausencia sin justificar: {user.get_full_name()} — hora pactada {hora_entrada.strftime("%H:%M")}',
        from_email    = settings.DEFAULT_FROM_EMAIL,
        recipient_list= [empresa.email_rrhh],
        html_message  = html,
        fail_silently = False,
    )


def _enviar_alerta_exceso(user, perfil, empresa, horas, ahora):
    """Envía email HTML de alerta de exceso de jornada al RRHH."""
    asunto = f'🚨 Exceso de jornada — {user.get_full_name()} ({int(horas)}h)'
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
      body{{font-family:system-ui,sans-serif;background:#f7f7f5;padding:20px}}
      .card{{background:#fff;border-radius:12px;max-width:520px;margin:0 auto;
        border:1px solid #e0e0e0;overflow:hidden}}
      .head{{background:#7a4a00;color:#fff;padding:16px 24px}}
      .head h2{{margin:0;font-size:16px;font-weight:500}}
      .body{{padding:20px 24px}}
      .row{{display:flex;justify-content:space-between;padding:8px 0;
        border-bottom:1px solid #f0f0f0;font-size:13px}}
      .lbl{{color:#888}}.val{{font-weight:500}}
      .foot{{background:#f7f7f5;padding:12px 24px;font-size:11px;color:#999;text-align:center}}
    </style></head>
    <body><div class="card">
      <div class="head"><h2>🚨 Alerta de Fatiga Laboral</h2><p style="margin:4px 0 0;opacity:.7;font-size:12px">{empresa.nombre}</p></div>
      <div class="body">
        <p style="font-size:13px;margin-bottom:16px">El siguiente trabajador lleva <strong>{int(horas)} horas</strong> sin registrar salida:</p>
        <div class="row"><span class="lbl">Trabajador</span><span class="val">{user.get_full_name()}</span></div>
        <div class="row"><span class="lbl">RUT</span><span class="val">{perfil.rut or 'S/I'}</span></div>
        <div class="row"><span class="lbl">Cargo</span><span class="val">{perfil.cargo or 'S/I'}</span></div>
        <div class="row"><span class="lbl">Horas trabajadas</span><span class="val" style="color:#7a4a00">{int(horas)}h {int((horas%1)*60)}m</span></div>
        <div class="row"><span class="lbl">Jornada pactada</span><span class="val">{perfil.jornada_diaria or 9}h</span></div>
        <div class="row"><span class="lbl">Hora de revisión</span><span class="val">{ahora.strftime('%H:%M')}</span></div>
      </div>
      <div class="foot">Alerta automática · Perseus Control · {empresa.nombre}</div>
    </div></body></html>
    """
    send_mail(
        subject       = asunto,
        message       = f'Exceso jornada: {user.get_full_name()} lleva {int(horas)}h trabajando.',
        from_email    = settings.DEFAULT_FROM_EMAIL,
        recipient_list= [empresa.email_rrhh],
        html_message  = html,
        fail_silently = False,
    )