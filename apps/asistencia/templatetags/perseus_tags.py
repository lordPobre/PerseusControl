"""
Perseus v4 — templatetags/perseus_tags.py
Filtros personalizados para templates.
"""
from django import template

register = template.Library()


@register.filter
def imagen_url(campo):
    """
    Retorna la URL correcta de un ImageField o URLField.
    Maneja tanto rutas locales (con .url) como URLs completas de Cloudinary.
    """
    if not campo:
        return ''
    # Si ya es una URL completa (Cloudinary), retornarla directo
    valor = str(campo)
    if valor.startswith('http'):
        return valor
    # Si es un ImageField con archivo, usar .url
    try:
        return campo.url
    except Exception:
        return valor
