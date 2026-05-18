"""Perseus v4 — views/ia.py"""
import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
@login_required
def mejorar_justificacion_ia(request):
    """Mejora el texto de una justificación usando Gemini."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data  = json.loads(request.body)
        texto = data.get('texto', '').strip()

        if len(texto) < 5:
            return JsonResponse({'error': 'Texto demasiado corto.'}, status=400)

        if not settings.GEMINI_API_KEY:
            return JsonResponse({'error': 'IA no configurada.'}, status=503)

        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)

        model  = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            'Actúa como experto en RRHH chileno. '
            'Reescribe este texto informal en una justificación formal y profesional '
            'para un registro de asistencia laboral. '
            'Solo devuelve el texto mejorado, sin explicaciones ni comillas:\n\n'
            f'"{texto}"'
        )
        resp = model.generate_content(prompt)
        return JsonResponse({'texto_mejorado': resp.text.strip()})

    except Exception as e:
        logger.error(f"IA error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
