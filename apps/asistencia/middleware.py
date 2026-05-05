"""
Perseus v4 — middleware.py
EmpresaActivaMiddleware: inyecta request.empresa para cada request
de un usuario autenticado.
"""


class EmpresaActivaMiddleware:
    """
    Pone request.empresa disponible en todas las vistas.
    Para usuarios no autenticados o sin perfil: request.empresa = None.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa = None

        if request.user.is_authenticated:
            perfil = getattr(request.user, 'perfil', None)
            if perfil:
                request.empresa = perfil.empresa

        response = self.get_response(request)
        return response
