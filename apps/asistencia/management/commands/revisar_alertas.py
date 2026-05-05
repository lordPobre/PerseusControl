"""
Perseus v4 — management/commands/revisar_alertas.py
Detecta ausencias y excesos de jornada. Ejecutar con cron o Celery beat.

Uso: python manage.py revisar_alertas
Cron sugerido: */30 * * * * (cada 30 minutos en días hábiles)
"""
import logging
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta, datetime

from apps.asistencia.models import (
    Empresa, Marcacion, LogAlerta, Feriado, Vacacion, LicenciaMedica
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Revisa ausencias y exceso de jornada por empresa y envía alertas.'

    def handle(self, *args, **kwargs):
        hoy   = timezone.localdate()
        ahora = timezone.localtime(timezone.now())

        # No ejecutar en fines de semana
        if hoy.weekday() >= 5:
            self.stdout.write('Fin de semana. Sin alertas.')
            return

        # No ejecutar en feriados
        if Feriado.objects.filter(fecha=hoy).exists():
            feriado = Feriado.objects.get(fecha=hoy)
            self.stdout.write(f'Feriado: {feriado.descripcion}. Sin alertas.')
            return

        self.stdout.write(f'Revisando alertas: {ahora.strftime("%d/%m/%Y %H:%M")}')

        for empresa in Empresa.objects.filter(activa=True):
            if not empresa.email_rrhh:
                continue

            self._revisar_empresa(empresa, hoy, ahora)

        self.stdout.write(self.style.SUCCESS('Revisión completada.'))

    def _revisar_empresa(self, empresa, hoy, ahora):
        usuarios = User.objects.filter(
            perfil__empresa=empresa,
            is_active=True,
            is_staff=False,
        ).select_related('perfil')

        remitente = f'Alertas Perseus <{settings.DEFAULT_FROM_EMAIL}>'

        for user in usuarios:
            perfil = getattr(user, 'perfil', None)
            if not perfil or not perfil.debe_trabajar_hoy():
                continue

            # Excluir con vacaciones o licencia activa
            si_vacacion = Vacacion.objects.filter(
                trabajador=user, inicio__lte=hoy, fin__gte=hoy, estado='APROBADA'
            ).exists()
            si_licencia = LicenciaMedica.objects.filter(
                trabajador=user, inicio__lte=hoy, fin__gte=hoy
            ).exists()
            if si_vacacion or si_licencia:
                continue

            hora_entrada = perfil.hora_entrada
            jornada_h    = perfil.jornada_diaria or 9
            entrada_dt   = timezone.make_aware(
                datetime.combine(hoy, hora_entrada)
            )
            limite_aus   = entrada_dt + timedelta(minutes=45)

            # ── ALERTA 1: Ausencia ─────────────────────────────
            if ahora > limite_aus:
                tiene_marca = Marcacion.objects.filter(
                    trabajador=user, timestamp__date=hoy, tipo='ENTRADA'
                ).exists()

                if not tiene_marca:
                    ya_avisado = LogAlerta.objects.filter(
                        trabajador=user, tipo='AUSENCIA', fecha=hoy
                    ).exists()

                    if not ya_avisado:
                        self._enviar_alerta(
                            remitente, empresa.email_rrhh,
                            f'⚠️ Ausencia: {user.get_full_name()}',
                            (
                                f'Empresa: {empresa.nombre}\n'
                                f'Trabajador: {user.get_full_name()}\n'
                                f'RUT: {perfil.rut or "S/I"}\n\n'
                                f'No ha registrado entrada.\n'
                                f'Hora pactada: {hora_entrada.strftime("%H:%M")}\n'
                                f'Hora revisión: {ahora.strftime("%H:%M")}'
                            )
                        )
                        LogAlerta.objects.create(
                            trabajador=user, empresa=empresa,
                            tipo='AUSENCIA', fecha=hoy
                        )
                        self.stdout.write(f'  Ausencia: {user.username}')

            # ── ALERTA 2: Exceso de jornada ────────────────────
            ultima = Marcacion.objects.filter(
                trabajador=user, timestamp__date=hoy
            ).order_by('-timestamp').first()

            if ultima and ultima.tipo in ('ENTRADA', 'FIN_COLACION'):
                primera = Marcacion.objects.filter(
                    trabajador=user, timestamp__date=hoy, tipo='ENTRADA'
                ).order_by('timestamp').first()

                if primera:
                    horas = (ahora - primera.timestamp).total_seconds() / 3600
                    if horas > jornada_h + 2:
                        ya_avisado = LogAlerta.objects.filter(
                            trabajador=user, tipo='EXCESO_HORAS', fecha=hoy
                        ).exists()
                        if not ya_avisado:
                            self._enviar_alerta(
                                remitente, empresa.email_rrhh,
                                f'🚨 Exceso jornada: {user.get_full_name()}',
                                (
                                    f'Empresa: {empresa.nombre}\n'
                                    f'Trabajador: {user.get_full_name()}\n\n'
                                    f'Lleva {int(horas)}h trabajando.\n'
                                    f'Jornada pactada: {jornada_h}h.\n'
                                    f'Favor verificar su salida.'
                                )
                            )
                            LogAlerta.objects.create(
                                trabajador=user, empresa=empresa,
                                tipo='EXCESO_HORAS', fecha=hoy
                            )
                            self.stdout.write(f'  Exceso: {user.username}')

    def _enviar_alerta(self, remitente, destinatario, asunto, mensaje):
        try:
            send_mail(asunto, mensaje, remitente, [destinatario], fail_silently=True)
        except Exception as e:
            logger.warning(f"Error enviando alerta: {e}")
