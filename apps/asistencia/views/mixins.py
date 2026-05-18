"""
Perseus v4 — views/mixins.py
Mixins y decoradores de permisos reutilizables para todas las vistas.
"""
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def requiere_perfil(func):
    """Redirige si el usuario no tiene perfil asociado."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'perfil'):
            messages.error(request, 'Tu usuario no tiene un perfil laboral asignado. Contacta a administración.')
            return redirect('dashboard')
        return func(request, *args, **kwargs)
    return wrapper


def requiere_empresa(func):
    """Redirige si el usuario no tiene empresa asignada."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not perfil or not perfil.empresa:
            messages.error(request, 'Tu usuario no tiene empresa asignada.')
            return redirect('dashboard')
        return func(request, *args, **kwargs)
    return wrapper


def requiere_empleador(func):
    """Solo EMPLEADOR o SUPERADMIN pueden acceder."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.es_empleador())):
            messages.error(request, 'No tienes permiso para acceder a esta sección.')
            return redirect('dashboard')
        return func(request, *args, **kwargs)
    return wrapper


def requiere_fiscalizador(func):
    """Solo FISCALIZADOR puede acceder."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (perfil and perfil.es_fiscalizador()):
            messages.error(request, 'Acceso exclusivo para Fiscalizadores DT.')
            return redirect('dashboard')
        return func(request, *args, **kwargs)
    return wrapper


def requiere_superadmin(func):
    """Solo superusuario Django puede acceder."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'Acceso denegado.')
            return redirect('dashboard')
        return func(request, *args, **kwargs)
    return wrapper
