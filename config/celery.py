"""
Perseus v4 — config/celery.py
Configuración de Celery para tareas asíncronas y programadas.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Apuntar al settings de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('perseus')

# Leer configuración desde Django settings (prefijo CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodescubrir tareas en todas las apps instaladas
app.autodiscover_tasks()


# ── Schedule de tareas periódicas ─────────────────────────────
app.conf.beat_schedule = {

    # Revisar ausencias — cada 30 min de Lun a Vie
    'revisar-ausencias': {
        'task':     'apps.asistencia.tasks.revisar_ausencias',
        'schedule': crontab(
            minute='*/30',      # cada 30 minutos
            hour='7-20',        # entre 7:00 y 20:00
            day_of_week='1-5',  # Lunes a Viernes
        ),
    },

    # Revisar exceso de jornada — cada 30 min de Lun a Sáb
    'revisar-exceso-jornada': {
        'task':     'apps.asistencia.tasks.revisar_exceso_jornada',
        'schedule': crontab(
            minute='*/30',
            hour='7-22',
            day_of_week='1-6',  # Lunes a Sábado
        ),
    },

    # Limpieza de logs de alerta — diario a las 2 AM
    'limpiar-logs-alertas': {
        'task':     'apps.asistencia.tasks.limpiar_logs_alertas',
        'schedule': crontab(hour=2, minute=0),
    },
}
