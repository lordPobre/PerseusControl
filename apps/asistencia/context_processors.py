"""
Perseus v4 — context_processors.py
Inyecta variables globales en todos los templates.
"""
from .models import SolicitudMarca


def empresa_activa(request):
    """
    Pone disponibles en todos los templates:
      - empresa_activa   → objeto Empresa del usuario logueado
      - perfil_usuario   → Perfil del usuario logueado
      - solicitudes_pendientes_count → badge para el sidebar
    """
    ctx = {
        'empresa_activa':              None,
        'perfil_usuario':              None,
        'solicitudes_pendientes_count': 0,
    }

    if not request.user.is_authenticated:
        return ctx

    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return ctx

    ctx['perfil_usuario']  = perfil
    ctx['empresa_activa']  = perfil.empresa

    # Contar solicitudes de marca pendientes PARA este trabajador
    # (las que le mandó RRHH para que acepte/rechace)
    ctx['solicitudes_pendientes_count'] = (
        SolicitudMarca.objects
        .filter(trabajador=request.user, estado='PENDIENTE')
        .exclude(solicitante=request.user)
        .count()
    )

    return ctx
