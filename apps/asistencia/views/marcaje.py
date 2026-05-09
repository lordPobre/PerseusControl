"""
Perseus v4 — views/marcaje.py
Registro de marcaciones con GPS, foto, hash SHA-256 y NTP Chile.
Art. 33 Código del Trabajo.
"""
import base64
import json
import logging
import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils import timezone
from django.utils.html import strip_tags

from apps.asistencia.models import Marcacion, Empresa
from apps.asistencia.ntp import obtener_timestamp_ntp
from .mixins import requiere_perfil

logger = logging.getLogger(__name__)


@login_required
@requiere_perfil
def registrar_marca(request):
    """
    Endpoint principal de marcaje. Recibe JSON con:
      - tipo: ENTRADA | INICIO_COLACION | FIN_COLACION | SALIDA
      - latitud, longitud
      - foto_base64
      - animo (solo SALIDA): FELIZ | NEUTRAL | MOLESTO
      - comentario_animo
      - fecha_offline (ISO 8601, para sincronización offline)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    # ── Parsear body ──────────────────────────────────────────
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)

    tipo             = data.get('tipo', 'ENTRADA')
    raw_lat          = data.get('latitud')
    raw_lon          = data.get('longitud')
    foto_b64         = data.get('foto_base64', '')
    animo            = data.get('animo')
    comentario_animo = data.get('comentario_animo', '')
    fecha_offline    = data.get('fecha_offline')
    precision_gps    = data.get('precision_gps')

    # ── Validar tipo ──────────────────────────────────────────
    tipos_validos = [t[0] for t in Marcacion.TIPO_CHOICES]
    if tipo not in tipos_validos:
        return JsonResponse({'error': f'Tipo de marca inválido: {tipo}'}, status=400)

    # ── Timestamp (NTP oficial o offline) ─────────────────────
    if fecha_offline:
        try:
            timestamp = datetime.datetime.fromisoformat(
                fecha_offline.replace('Z', '+00:00')
            )
        except ValueError:
            timestamp = timezone.now()
    else:
        # Intentar NTP Chile, fallback a hora del servidor
        timestamp = obtener_timestamp_ntp()

    # ── GPS ───────────────────────────────────────────────────
    lat, lon = None, None
    if raw_lat and str(raw_lat).lower() not in ('', 'nan', 'none'):
        try:
            from decimal import Decimal, ROUND_DOWN, InvalidOperation
            lat = Decimal(str(raw_lat)).quantize(Decimal('0.0000001'), rounding=ROUND_DOWN)
            lon = Decimal(str(raw_lon)).quantize(Decimal('0.0000001'), rounding=ROUND_DOWN)
        except (InvalidOperation, TypeError, ValueError):
            pass

    # ── Validaciones hardware (entrada y salida requieren GPS + foto) ──
    if tipo in ('ENTRADA', 'SALIDA'):
        if lat is None:
            return JsonResponse(
                {'error': 'GPS requerido para marcar entrada/salida. Activa la ubicación.'},
                status=400
            )
        if not foto_b64:
            return JsonResponse(
                {'error': 'Foto requerida para marcar entrada/salida.'},
                status=400
            )

    # ── Geocodificación ───────────────────────────────────────
    direccion = ''
    if lat and lon:
        direccion = _geocodificar(lat, lon)

    # ── Construir objeto Marcacion ────────────────────────────
    marca = Marcacion(
        trabajador       = request.user,
        tipo             = tipo,
        timestamp        = timestamp,
        latitud          = lat,
        longitud         = lon,
        direccion        = direccion,
        precision_gps    = precision_gps,
        ip_address       = _get_ip(request),
        animo            = animo if tipo == 'SALIDA' else None,
        comentario_animo = comentario_animo if tipo == 'SALIDA' else '',
    )

    # ── Foto biométrica → R2 via django-storages ─────────────
    if foto_b64:
        try:
            if ';base64,' in foto_b64:
                _, imgstr = foto_b64.split(';base64,')
            else:
                imgstr = foto_b64
            imagen_bytes = base64.b64decode(imgstr)
            ts = int(timezone.now().timestamp())
            from django.core.files.base import ContentFile
            marca.foto = ContentFile(
                imagen_bytes,
                name=f'marcas/{timezone.localdate().year}/{timezone.localdate().month:02d}/marca_{request.user.id}_{ts}.jpg'
            )
        except Exception as e:
            logger.warning(f"Error procesando foto de {request.user.username}: {e}")
            marca.foto = None

    # ── Guardar (calcula hash automáticamente en model.save()) ───
    try:
        marca.save()
    except Exception as e:
        logger.error(f"Error guardando marca de {request.user.username}: {e}")
        return JsonResponse({'error': f'Error al registrar: {str(e)}'}, status=500)

    # ── Email de comprobante (async en producción idealmente) ─
    _enviar_comprobante(request.user, marca)

    logger.info(
        f"Marca registrada: {request.user.username} | {tipo} | "
        f"{timezone.localtime(timestamp).strftime('%d/%m/%Y %H:%M:%S')}"
    )

    return JsonResponse({
        'status': 'ok',
        'mensaje': f'{tipo.replace("_", " ").title()} registrada correctamente.',
        'timestamp': timezone.localtime(marca.timestamp).strftime('%H:%M:%S'),
    })


# ── Helpers internos ──────────────────────────────────────────

def _geocodificar(lat, lon):
    """Convierte coordenadas a dirección textual."""
    try:
        from geopy.geocoders import Nominatim
        geo = Nominatim(user_agent='perseus_v4', timeout=4)
        loc = geo.reverse(f'{lat}, {lon}', timeout=4)
        return loc.address[:280] if loc else ''
    except Exception as e:
        logger.debug(f"Geocoding falló: {e}")
        return ''


def _get_ip(request):
    """Obtiene IP real del cliente."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _enviar_comprobante(user, marca):
    """Envía email HTML con comprobante de marcaje."""
    if not user.email:
        return

    try:
        from django.conf import settings as cfg
        hora    = timezone.localtime(marca.timestamp).strftime('%H:%M:%S')
        fecha   = timezone.localtime(marca.timestamp).strftime('%d/%m/%Y')
        empresa = getattr(getattr(user, 'perfil', None), 'empresa', None)
        nom_emp = empresa.nombre if empresa else 'Perseus Control'
        email_rrhh = empresa.email_rrhh if empresa else None
        lat, lon   = marca.latitud, marca.longitud
        link_maps  = f'https://www.google.com/maps?q={lat},{lon}' if lat else '#'

        html = f"""
        <!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>
          body{{font-family:system-ui,sans-serif;color:#333;background:#f7f7f5;margin:0;padding:20px}}
          .card{{background:#fff;border-radius:12px;overflow:hidden;max-width:520px;margin:0 auto;border:1px solid #e0e0e0}}
          .head{{background:#1a1a1a;color:#fff;padding:18px 24px}}
          .head h2{{margin:0;font-size:16px;font-weight:500}}
          .head p{{margin:4px 0 0;opacity:.65;font-size:12px}}
          .body{{padding:24px}}
          .row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:13px}}
          .lbl{{color:#888}}
          .val{{font-weight:500}}
          .tipo-badge{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;
            background:{'#e8f5ee' if 'ENTRADA' in marca.tipo else '#fdf0f0'};
            color:{'#1a6644' if 'ENTRADA' in marca.tipo else '#991f1f'}}}
          .btn{{display:inline-block;padding:6px 14px;background:#1a6644;color:#fff;
            text-decoration:none;border-radius:6px;font-size:12px;margin-top:6px}}
          .foot{{background:#f7f7f5;padding:12px 24px;font-size:11px;color:#999;text-align:center}}
        </style></head><body>
        <div class="card">
          <div class="head">
            <h2>Comprobante de Asistencia</h2>
            <p>{nom_emp}</p>
          </div>
          <div class="body">
            <p style="margin-bottom:16px;font-size:13px">
              Hola <strong>{user.first_name} {user.last_name}</strong>, tu marcación fue registrada exitosamente.
            </p>
            <div class="row"><span class="lbl">Tipo</span>
              <span class="val"><span class="tipo-badge">{marca.get_tipo_display()}</span></span></div>
            <div class="row"><span class="lbl">Fecha</span><span class="val">{fecha}</span></div>
            <div class="row"><span class="lbl">Hora registrada</span><span class="val">{hora}</span></div>
            <div class="row"><span class="lbl">Ubicación</span>
              <span class="val" style="text-align:right;max-width:280px">
                {marca.direccion or 'Coordenadas GPS'}<br>
                {'<a href="'+link_maps+'" class="btn">Ver en mapa</a>' if lat else ''}
              </span>
            </div>
            <div class="row"><span class="lbl">Estado</span>
              <span class="val" style="color:#1a6644">Validado correctamente</span></div>
          </div>
          <div class="foot">
            Mensaje automático generado por Perseus Control · {nom_emp}<br>
            No responder a este correo.
          </div>
        </div></body></html>
        """

        destinatarios = [user.email]
        if email_rrhh and email_rrhh != user.email:
            destinatarios.append(email_rrhh)

        send_mail(
            subject       = f'[Perseus] {marca.get_tipo_display()} — {user.get_full_name()} {fecha} {hora}',
            message       = strip_tags(html),
            from_email    = cfg.DEFAULT_FROM_EMAIL,
            recipient_list= destinatarios,
            html_message  = html,
            fail_silently = True,
        )
    except Exception as e:
        logger.warning(f"Error enviando comprobante a {user.username}: {e}")
