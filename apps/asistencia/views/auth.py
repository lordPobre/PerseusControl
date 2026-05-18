"""
Perseus v4 — views/auth.py
Autenticación, cambio de contraseña obligatorio y Service Worker.
"""
import logging
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


class ServiceWorkerView(TemplateView):
    """Sirve el Service Worker con el content-type correcto."""
    template_name = 'asistencia/sw.js'
    content_type  = 'application/javascript'


@login_required
def cambiar_password_obligatorio(request):
    """
    Fuerza cambio de contraseña en primer ingreso.
    Mientras cambiar_pass=True, el trabajador no puede acceder al sistema.
    """
    perfil = getattr(request.user, 'perfil', None)

    # Si ya cambió la contraseña, redirigir al dashboard
    if perfil and not perfil.cambiar_pass:
        return redirect('dashboard')

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # No cerrar sesión
            if perfil:
                perfil.cambiar_pass = False
                perfil.save(update_fields=['cambiar_pass'])
            messages.success(request, '¡Contraseña actualizada! Ya puedes usar el sistema.')
            logger.info(f"Contraseña cambiada: {user.username}")
            return redirect('dashboard')
        else:
            messages.error(request, 'Corrige los errores indicados.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'asistencia/cambiar_pass.html', {'form': form})
