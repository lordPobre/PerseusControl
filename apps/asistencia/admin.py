from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Empresa, Perfil, Marcacion, SolicitudMarca,
    Feriado, Vacacion, LicenciaMedica, DiaAdministrativo,
    LogAlerta, Turno, AsignacionTurno
)


# ── Inline Perfil en User ──────────────────────────────────────
class PerfilInline(admin.StackedInline):
    model       = Perfil
    can_delete  = False
    verbose_name_plural = 'Perfil laboral'
    fk_name     = 'usuario'
    fields      = ('empresa', 'rut', 'cargo', 'rol',
                   'hora_entrada', 'jornada_diaria',
                   'trabaja_lunes', 'trabaja_martes', 'trabaja_miercoles',
                   'trabaja_jueves', 'trabaja_viernes',
                   'trabaja_sabado', 'trabaja_domingo',
                   'cambiar_pass')


class UserAdmin(BaseUserAdmin):
    def get_inlines(self, request, obj=None):
        return [PerfilInline] if obj else []

if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ── Empresa ────────────────────────────────────────────────────
@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'rut', 'email_rrhh', 'activa', 'creada_en')
    list_filter   = ('activa',)
    search_fields = ('nombre', 'rut')


# ── Perfil ─────────────────────────────────────────────────────
@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display  = ('usuario', 'empresa', 'cargo', 'rol', 'activo')
    list_filter   = ('rol', 'empresa', 'activo')
    search_fields = ('usuario__username', 'usuario__first_name', 'rut')


# ── Marcacion ──────────────────────────────────────────────────
@admin.register(Marcacion)
class MarcacionAdmin(admin.ModelAdmin):
    list_display  = ('trabajador', 'empresa', 'tipo', 'timestamp', 'estado', 'es_manual')
    list_filter   = ('tipo', 'estado', 'empresa', 'es_manual')
    search_fields = ('trabajador__first_name', 'trabajador__last_name',
                     'trabajador__perfil__rut')
    date_hierarchy = 'timestamp'
    readonly_fields = ('hash_previo', 'hash_actual')


# ── Feriado ────────────────────────────────────────────────────
@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion', 'es_irrenunciable')
    ordering     = ['fecha']


# ── Vacación ───────────────────────────────────────────────────
@admin.register(Vacacion)
class VacacionAdmin(admin.ModelAdmin):
    list_display  = ('trabajador', 'inicio', 'fin', 'dias_habiles', 'estado')
    list_filter   = ('estado',)
    search_fields = ('trabajador__username', 'trabajador__first_name')


# ── Licencia ───────────────────────────────────────────────────
@admin.register(LicenciaMedica)
class LicenciaAdmin(admin.ModelAdmin):
    list_display  = ('trabajador', 'tipo', 'inicio', 'fin', 'folio')
    list_filter   = ('tipo',)


# ── Otros ──────────────────────────────────────────────────────
admin.site.register(SolicitudMarca)
admin.site.register(DiaAdministrativo)
admin.site.register(LogAlerta)
admin.site.register(Turno)
admin.site.register(AsignacionTurno)
