"""
Perseus v4 — crear_superusuario.py
Crea el superusuario inicial desde variables de entorno.
Uso: python manage.py crear_superusuario
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decouple import config


class Command(BaseCommand):
    help = 'Crea el superusuario inicial desde variables de entorno'

    def handle(self, *args, **kwargs):
        username = config('ADMIN_USERNAME', default='admin')
        email    = config('ADMIN_EMAIL',    default='admin@example.com')
        password = config('ADMIN_PASSWORD', default='')

        if not password:
            self.stdout.write(self.style.ERROR(
                'Define ADMIN_PASSWORD en las variables de entorno de Railway.'
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'El usuario "{username}" ya existe.'
            ))
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Superusuario "{username}" creado correctamente.'
        ))
