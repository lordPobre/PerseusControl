"""
Perseus v4 — ntp.py
Obtiene la hora oficial de Chile desde el servidor NTP del SHOA.
Fallback a hora del servidor si no hay conexión.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def obtener_timestamp_ntp():
    """
    Consulta el servidor NTP del SHOA (Armada de Chile).
    Retorna datetime con timezone UTC.
    Fallback a datetime.now(UTC) si falla.
    """
    try:
        import ntplib
        cliente   = ntplib.NTPClient()
        respuesta = cliente.request('ntp.shoa.cl', version=3, timeout=2)
        hora_utc  = datetime.fromtimestamp(respuesta.tx_time, timezone.utc)
        logger.debug(f"NTP SHOA: {hora_utc}")
        return hora_utc
    except Exception as e:
        logger.warning(f"NTP SHOA no disponible ({e}), usando hora del servidor.")
        return datetime.now(timezone.utc)
