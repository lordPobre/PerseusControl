"""
Perseus v4 — urls.py
Todas las rutas de la aplicación, organizadas por módulo.
"""
from django.urls import path
from django.contrib.auth.decorators import login_required

from .views.auth      import ServiceWorkerView, cambiar_password_obligatorio
from .views.dashboard import dashboard, mis_marcas, privacidad, ayuda
from .views.perfil    import perfil
from .views.marcaje   import registrar_marca
from .views.ausencias import ausencias, aprobar_licencia
from .views.rrhh      import (
    panel_rrhh, panel_empresa,
    responder_solicitud, crear_solicitud_trabajador,
    gestionar_ausencias, aprobar_vacacion,
    mis_vacaciones, mis_dias_admin, gestionar_dia_admin,
    turnos, importar_nomina, cargar_feriados,
)
from .views.fiscalizador import panel_fiscalizador
from .views.reportes  import (
    exportar_excel_empresa, exportar_clima,
    exportar_reporte_fiscalizacion, exportar_remuneraciones,
    generar_pdf_trabajador,
)
from .views.ia import mejorar_justificacion_ia

urlpatterns = [

    # ── Autenticación ──────────────────────────────────────────
    path('cambiar-clave/', cambiar_password_obligatorio, name='cambiar_password'),

    # ── Dashboard ──────────────────────────────────────────────
    path('',             dashboard,  name='dashboard'),
    path('mis-marcas/',  mis_marcas, name='mis_marcas'),
    path('perfil/',   perfil,  name='perfil'),
    path('privacidad/',  privacidad, name='privacidad'),
    path('ayuda/',       ayuda,      name='ayuda'),

    # ── Marcaje (endpoint JSON) ────────────────────────────────
    path('api/marcar/', registrar_marca, name='registrar_marca'),

    # ── Solicitudes de marca ───────────────────────────────────
    path('solicitudes/crear/',
         crear_solicitud_trabajador, name='crear_solicitud'),
    path('solicitudes/<int:sol_id>/<str:accion>/',
         responder_solicitud, name='responder_solicitud'),

    # ── RRHH ──────────────────────────────────────────────────
    path('rrhh/panel/',          panel_rrhh,    name='panel_rrhh'),
    path('empresa/panel/',       panel_empresa, name='panel_empresa'),

    # Ausencias
    path('rrhh/ausencias/',      gestionar_ausencias, name='gestionar_ausencias'),
    path('vacaciones/aprobar/<int:vac_id>/<str:estado>/',
         aprobar_vacacion, name='aprobar_vacacion'),
    path('rrhh/dia-admin/<int:sol_id>/<str:accion>/',
         gestionar_dia_admin, name='gestionar_dia_admin'),

    # Turnos
    path('rrhh/turnos/', turnos, name='turnos'),

    # ── Trabajador — autogestión ───────────────────────────────
    path('ausencias/',   ausencias, name='ausencias'),
    path('mis-vacaciones/',  ausencias, name='mis_vacaciones'),  # alias para compatibilidad
    path('mis-dias-admin/',  ausencias, name='mis_dias_admin'),  # alias para compatibilidad
    path('licencia/aprobar/<int:lic_id>/<str:estado>/',
         aprobar_licencia, name='aprobar_licencia'),

    # ── Fiscalizador DT ────────────────────────────────────────
    path('fiscalizacion/',    panel_fiscalizador,          name='panel_fiscalizador'),
    path('fiscalizacion/excel/', exportar_reporte_fiscalizacion, name='exportar_fiscalizacion'),

    # ── Reportes ───────────────────────────────────────────────
    path('reportes/excel/',        exportar_excel_empresa, name='exportar_excel'),
    path('reportes/clima/',        exportar_clima,         name='exportar_clima'),
    path('reportes/remuneraciones/', exportar_remuneraciones, name='reporte_remuneraciones'),
    path('mi-pdf/',                generar_pdf_trabajador, name='mi_pdf'),

    # ── Admin ─────────────────────────────────────────────────
    path('admin/importar-nomina/', importar_nomina,  name='importar_nomina'),
    path('admin/feriados/',        cargar_feriados,  name='cargar_feriados'),

    # ── IA ────────────────────────────────────────────────────
    path('api/mejorar-texto/', mejorar_justificacion_ia, name='mejorar_texto_ia'),
]