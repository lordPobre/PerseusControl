"""
Perseus v4 — signals.py
Crea automáticamente el Perfil cuando se registra un nuevo User.
"""
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Perfil


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    """Al crear un User, crea su Perfil asociado."""
    if created:
        Perfil.objects.get_or_create(usuario=instance)
