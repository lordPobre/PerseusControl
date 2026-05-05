"""
Perseus Control v4 — models.py
Diseño multitenant: cada Empresa es un tenant independiente.
Cumple Art. 22, 32, 33, 35, 67, 71 Código del Trabajo Chile.
"""
import hashlib
import datetime
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


# ══════════════════════════════════════════════════════════════
# TENANT: EMPRESA
# ══════════════════════════════════════════════════════════════

class Empresa(models.Model):
    """Tenant principal. Cada empresa es un espacio aislado."""

    nombre       = models.CharField(max_length=150, verbose_name="Nombre empresa")
    razon_social = models.CharField(max_length=200, blank=True, null=True,
                                    verbose_name="Razón social (SII)")
    rut          = models.CharField(max_length=12, blank=True, null=True,
                                    verbose_name="RUT empresa",
                                    help_text="Ej: 76.123.456-K")
    direccion    = models.CharField(max_length=255, blank=True, null=True,
                                    verbose_name="Dirección comercial")
    ciudad       = models.CharField(max_length=100, blank=True, null=True)
    email_rrhh   = models.EmailField(blank=True, null=True,
                                     verbose_name="Email RRHH (alertas)")
    telefono     = models.CharField(max_length=20, blank=True, null=True)
    logo         = models.ImageField(upload_to='logos/', null=True, blank=True,
                                     verbose_name="Logo empresa")
    activa       = models.BooleanField(default=True)
    creada_en    = models.DateTimeField(auto_now_add=True)

    # Configuración laboral por defecto para la empresa
    tolerancia_atraso_min = models.PositiveIntegerField(
        default=10,
        verbose_name="Tolerancia atraso (minutos)",
        help_text="Minutos de gracia antes de contar como atraso"
    )
    jornada_semanal_horas = models.PositiveIntegerField(
        default=45,
        verbose_name="Horas jornada semanal",
        help_text="Máximo legal: 45 horas (Art. 22 CT)"
    )

    class Meta:
        verbose_name         = "Empresa"
        verbose_name_plural  = "Empresas"
        ordering             = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.rut or 'sin RUT'})"


# ══════════════════════════════════════════════════════════════
# PERFIL DE USUARIO (extensión de User)
# ══════════════════════════════════════════════════════════════

class Perfil(models.Model):
    """Extiende User con datos laborales y rol dentro del sistema."""

    ROL_CHOICES = [
        ('TRABAJADOR',   'Trabajador'),
        ('EMPLEADOR',    'Empleador / RRHH'),
        ('FISCALIZADOR', 'Fiscalizador DT'),
        ('SUPERADMIN',   'Superadministrador'),
    ]

    usuario  = models.OneToOneField(User, on_delete=models.CASCADE,
                                    related_name='perfil')
    empresa  = models.ForeignKey(Empresa, on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name='trabajadores')
    rut      = models.CharField(max_length=12, blank=True, null=True,
                                verbose_name="RUT trabajador")
    cargo    = models.CharField(max_length=100, blank=True,
                                verbose_name="Cargo / Puesto")
    rol      = models.CharField(max_length=20, choices=ROL_CHOICES,
                                default='TRABAJADOR')

    # Jornada laboral personalizada (sobreescribe defaults de empresa)
    hora_entrada   = models.TimeField(default=datetime.time(9, 0),
                                      verbose_name="Hora entrada oficial")
    jornada_diaria = models.PositiveIntegerField(
        default=9,
        verbose_name="Horas por jornada diaria"
    )

    # Días que le corresponde trabajar
    trabaja_lunes    = models.BooleanField(default=True,  verbose_name="Lunes")
    trabaja_martes   = models.BooleanField(default=True,  verbose_name="Martes")
    trabaja_miercoles= models.BooleanField(default=True,  verbose_name="Miércoles")
    trabaja_jueves   = models.BooleanField(default=True,  verbose_name="Jueves")
    trabaja_viernes  = models.BooleanField(default=True,  verbose_name="Viernes")
    trabaja_sabado   = models.BooleanField(default=False, verbose_name="Sábado")
    trabaja_domingo  = models.BooleanField(default=False, verbose_name="Domingo")

    # Control de acceso
    cambiar_pass = models.BooleanField(
        default=True,
        verbose_name="Debe cambiar contraseña en primer ingreso"
    )
    activo = models.BooleanField(default=True)
    telefono = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name="Teléfono de contacto"
    )

    class Meta:
        verbose_name        = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return f"{self.usuario.get_full_name()} — {self.empresa}"

    def debe_trabajar_hoy(self):
        """Retorna True si al usuario le corresponde trabajar hoy."""
        mapa = {
            0: self.trabaja_lunes,
            1: self.trabaja_martes,
            2: self.trabaja_miercoles,
            3: self.trabaja_jueves,
            4: self.trabaja_viernes,
            5: self.trabaja_sabado,
            6: self.trabaja_domingo,
        }
        return mapa.get(timezone.localdate().weekday(), False)

    def es_empleador(self):
        return self.rol in ('EMPLEADOR', 'SUPERADMIN') or self.usuario.is_superuser

    def es_fiscalizador(self):
        return self.rol == 'FISCALIZADOR'

    def es_superadmin(self):
        return self.rol == 'SUPERADMIN' or self.usuario.is_superuser


# ══════════════════════════════════════════════════════════════
# TURNO (gestión de turnos rotativos)
# ══════════════════════════════════════════════════════════════

class Turno(models.Model):
    """Define un tipo de turno (Mañana, Tarde, Noche, etc.)"""

    empresa      = models.ForeignKey(Empresa, on_delete=models.CASCADE,
                                     related_name='turnos')
    nombre       = models.CharField(max_length=80, verbose_name="Nombre del turno")
    hora_inicio  = models.TimeField(verbose_name="Hora inicio")
    hora_fin     = models.TimeField(verbose_name="Hora fin")
    color        = models.CharField(max_length=7, default='#1a6644',
                                    help_text="Color HEX para el calendario")
    activo       = models.BooleanField(default=True)

    class Meta:
        verbose_name        = "Turno"
        verbose_name_plural = "Turnos"
        ordering            = ['hora_inicio']
        unique_together     = ('empresa', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M})"


class AsignacionTurno(models.Model):
    """Asigna un turno a un trabajador en una fecha específica."""

    trabajador = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='turnos_asignados')
    turno      = models.ForeignKey(Turno, on_delete=models.CASCADE)
    fecha      = models.DateField(verbose_name="Fecha de turno")

    class Meta:
        verbose_name        = "Asignación de turno"
        verbose_name_plural = "Asignaciones de turno"
        unique_together     = ('trabajador', 'fecha')
        ordering            = ['-fecha']

    def __str__(self):
        return f"{self.trabajador.get_full_name()} — {self.turno} el {self.fecha}"


# ══════════════════════════════════════════════════════════════
# MARCACIÓN (core DT — Art. 33 CT)
# ══════════════════════════════════════════════════════════════

class Marcacion(models.Model):
    """
    Registro de marcaje. Cada marca es inmutable tras su creación.
    La cadena de hash SHA-256 garantiza integridad ante la DT.
    """

    TIPO_CHOICES = [
        ('ENTRADA',        'Entrada'),
        ('INICIO_COLACION','Inicio colación'),
        ('FIN_COLACION',   'Fin colación'),
        ('SALIDA',         'Salida'),
    ]

    ESTADO_CHOICES = [
        ('VIGENTE',     'Vigente'),
        ('RECTIFICADA', 'Rectificada (histórico)'),
        ('ANULADA',     'Anulada'),
    ]

    ANIMO_CHOICES = [
        ('FELIZ',   'Motivado'),
        ('NEUTRAL', 'Normal'),
        ('MOLESTO', 'Bajo / Cansado'),
    ]

    # Relaciones
    trabajador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='marcaciones'
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='marcaciones',
        null=True  # se rellena automáticamente desde perfil en save()
    )

    # Datos del evento
    tipo      = models.CharField(max_length=20, choices=TIPO_CHOICES)
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y hora exacta (NTP)"
    )
    estado    = models.CharField(max_length=20, choices=ESTADO_CHOICES,
                                 default='VIGENTE')

    # Geolocalización
    latitud   = models.DecimalField(max_digits=11, decimal_places=7,
                                    null=True, blank=True)
    longitud  = models.DecimalField(max_digits=11, decimal_places=7,
                                    null=True, blank=True)
    direccion = models.CharField(max_length=300, blank=True,
                                 verbose_name="Dirección geocodificada")
    precision_gps = models.FloatField(null=True, blank=True,
                                      verbose_name="Precisión GPS (metros)")

    # Fotografía biométrica
    foto = models.ImageField(
        upload_to='marcas/%Y/%m/',
        null=True, blank=True,
        verbose_name="Foto de verificación"
    )

    # Metadatos técnicos
    ip_address        = models.GenericIPAddressField(null=True, blank=True)
    es_manual         = models.BooleanField(default=False,
                                            verbose_name="Marca ingresada manualmente")
    marca_reemplazada = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reemplazos'
    )
    observacion = models.TextField(blank=True)

    # Ánimo (solo en salida)
    animo            = models.CharField(max_length=10, choices=ANIMO_CHOICES,
                                        null=True, blank=True)
    comentario_animo = models.TextField(null=True, blank=True)

    # Alerta
    alerta_olvido_enviada = models.BooleanField(default=False)

    # Cadena de integridad SHA-256 (Art. 33 CT — inmutabilidad)
    hash_previo = models.CharField(max_length=64, blank=True,
                                   verbose_name="Hash registro anterior")
    hash_actual = models.CharField(max_length=64, blank=True, editable=False,
                                   verbose_name="Hash de este registro")

    class Meta:
        verbose_name        = "Marcación"
        verbose_name_plural = "Marcaciones"
        ordering            = ['-timestamp']
        indexes             = [
            models.Index(fields=['trabajador', 'timestamp']),
            models.Index(fields=['empresa', 'timestamp']),
            models.Index(fields=['tipo', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.trabajador.get_full_name()} — {self.tipo} {self.timestamp:%d/%m/%Y %H:%M}"

    def _calcular_hash(self):
        """Genera el hash SHA-256 encadenado con el registro anterior."""
        ultima = (
            Marcacion.objects
            .filter(trabajador=self.trabajador)
            .exclude(pk=self.pk)
            .order_by('-timestamp')
            .first()
        )
        prev = ultima.hash_actual if ultima else 'GENESIS_BLOCK_PERSEUS_V4'
        self.hash_previo = prev
        raw = (
            f"{self.trabajador_id}"
            f"{self.timestamp.isoformat()}"
            f"{self.tipo}"
            f"{self.latitud or ''}"
            f"{self.longitud or ''}"
            f"{prev}"
        )
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def clean(self):
        """Validaciones de integridad cronológica."""
        super().clean()
        if self.tipo == 'SALIDA' and self.trabajador_id:
            ultima_entrada = (
                Marcacion.objects
                .filter(trabajador_id=self.trabajador_id, tipo='ENTRADA')
                .exclude(pk=self.pk or 0)
                .order_by('-timestamp')
                .first()
            )
            if ultima_entrada and self.timestamp < ultima_entrada.timestamp:
                raise ValidationError(
                    f"No puedes registrar SALIDA ({self.timestamp:%H:%M}) "
                    f"antes de la ENTRADA ({ultima_entrada.timestamp:%H:%M})."
                )

    def save(self, *args, **kwargs):
        # Rellenar empresa desde perfil del trabajador
        if not self.empresa_id and hasattr(self, 'trabajador') and hasattr(self.trabajador, 'perfil'):
            self.empresa = self.trabajador.perfil.empresa

        # Calcular hash solo en creación
        if not self.pk:
            self.full_clean()
            self.hash_actual = self._calcular_hash()

        super().save(*args, **kwargs)


# ══════════════════════════════════════════════════════════════
# SOLICITUDES DE CORRECCIÓN DE MARCA
# ══════════════════════════════════════════════════════════════

class SolicitudMarca(models.Model):
    TIPO_CHOICES = [
        ('NUEVA',         'Nueva marca (olvido / falla técnica)'),
        ('RECTIFICACION', 'Corrección de hora existente'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de aprobación'),
        ('ACEPTADA',  'Aceptada'),
        ('RECHAZADA', 'Rechazada'),
    ]

    trabajador           = models.ForeignKey(User, on_delete=models.CASCADE,
                                             related_name='solicitudes_marca')
    solicitante          = models.ForeignKey(User, on_delete=models.PROTECT,
                                             related_name='solicitudes_creadas')
    tipo_solicitud       = models.CharField(max_length=20, choices=TIPO_CHOICES)
    estado               = models.CharField(max_length=20, choices=ESTADO_CHOICES,
                                            default='PENDIENTE')
    fecha_hora_propuesta = models.DateTimeField()
    tipo_marca_propuesta = models.CharField(max_length=20)
    motivo               = models.TextField()
    marca_original       = models.ForeignKey(Marcacion, on_delete=models.SET_NULL,
                                             null=True, blank=True)
    creado_en            = models.DateTimeField(auto_now_add=True)
    actualizado_en       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Solicitud de marca"
        verbose_name_plural = "Solicitudes de marca"
        ordering            = ['-creado_en']

    def __str__(self):
        return f"{self.tipo_solicitud} — {self.trabajador.get_full_name()} ({self.estado})"


# ══════════════════════════════════════════════════════════════
# FERIADOS (Art. 67 CT)
# ══════════════════════════════════════════════════════════════

class Feriado(models.Model):
    """Feriados legales Chile. Pueden ser nacionales o por empresa."""

    fecha       = models.DateField(unique=True)
    descripcion = models.CharField(max_length=150)
    es_irrenunciable = models.BooleanField(
        default=True,
        verbose_name="Feriado irrenunciable",
        help_text="Navidad, 1 de mayo, Fiestas Patrias, etc."
    )

    class Meta:
        verbose_name        = "Feriado"
        verbose_name_plural = "Feriados"
        ordering            = ['fecha']

    def __str__(self):
        return f"{self.fecha} — {self.descripcion}"


# ══════════════════════════════════════════════════════════════
# VACACIONES (Art. 71 CT)
# ══════════════════════════════════════════════════════════════

class Vacacion(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de aprobación'),
        ('APROBADA',  'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
    ]

    trabajador     = models.ForeignKey(User, on_delete=models.CASCADE,
                                       related_name='vacaciones')
    inicio         = models.DateField(verbose_name="Fecha inicio")
    fin            = models.DateField(verbose_name="Fecha fin")
    dias_habiles   = models.PositiveIntegerField(
        default=0,
        verbose_name="Días hábiles descontados",
        help_text="Se calcula automáticamente excluyendo feriados"
    )
    comentario     = models.CharField(max_length=300, blank=True)
    estado         = models.CharField(max_length=15, choices=ESTADO_CHOICES,
                                      default='PENDIENTE')
    aprobado_por   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='vacaciones_aprobadas')
    fecha_solicitud= models.DateTimeField(auto_now_add=True)
    comentario_rrhh= models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name        = "Vacación"
        verbose_name_plural = "Vacaciones"
        ordering            = ['-inicio']

    def __str__(self):
        return f"{self.trabajador.get_full_name()} — {self.inicio} al {self.fin}"

    def calcular_dias_habiles(self):
        """Calcula días hábiles descontando fines de semana y feriados."""
        from datetime import timedelta, date as date_type
        import datetime

        # Convertir a date si llegan como string
        inicio = self.inicio
        fin    = self.fin
        if isinstance(inicio, str):
            inicio = datetime.datetime.strptime(inicio, '%Y-%m-%d').date()
        if isinstance(fin, str):
            fin = datetime.datetime.strptime(fin, '%Y-%m-%d').date()

        feriados = set(
            Feriado.objects.filter(
                fecha__range=[inicio, fin]
            ).values_list('fecha', flat=True)
        )
        total  = 0
        actual = inicio
        while actual <= fin:
            if actual.weekday() < 5 and actual not in feriados:
                total += 1
            actual += timedelta(days=1)
        return total

    def save(self, *args, **kwargs):
        if self.inicio and self.fin:
            self.dias_habiles = self.calcular_dias_habiles()
        super().save(*args, **kwargs)


# ══════════════════════════════════════════════════════════════
# LICENCIA MÉDICA
# ══════════════════════════════════════════════════════════════

class LicenciaMedica(models.Model):
    TIPO_CHOICES = [
        ('ENFERMEDAD', 'Enfermedad común'),
        ('ACCIDENTE',  'Accidente laboral (ACHS/Mutual)'),
        ('MATERNAL',   'Pre/post natal'),
        ('OTRO',       'Otro motivo'),
    ]

    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de revisión'),
        ('APROBADA',  'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
    ]

    trabajador   = models.ForeignKey(User, on_delete=models.CASCADE,
                                     related_name='licencias')
    inicio       = models.DateField()
    fin          = models.DateField()
    tipo         = models.CharField(max_length=20, choices=TIPO_CHOICES,
                                    default='ENFERMEDAD')
    folio        = models.CharField(max_length=50, blank=True,
                                    verbose_name="N° folio licencia")
    documento    = models.FileField(upload_to='licencias/%Y/', blank=True, null=True,
                                    verbose_name="Documento PDF")
    observacion  = models.TextField(blank=True)
    estado       = models.CharField(max_length=15, choices=ESTADO_CHOICES,
                                    default='PENDIENTE')
    comentario_rrhh = models.CharField(max_length=300, blank=True)
    creada_en    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Licencia médica"
        verbose_name_plural = "Licencias médicas"
        ordering            = ['-inicio']

    def __str__(self):
        return f"{self.trabajador.get_full_name()} — {self.tipo} ({self.inicio} al {self.fin})"


# ══════════════════════════════════════════════════════════════
# DÍA ADMINISTRATIVO
# ══════════════════════════════════════════════════════════════

class DiaAdministrativo(models.Model):
    TIPO_JORNADA = [
        ('COMPLETO', 'Día completo'),
        ('MANANA',   'Media jornada mañana'),
        ('TARDE',    'Media jornada tarde'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO',  'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    trabajador     = models.ForeignKey(User, on_delete=models.CASCADE,
                                       related_name='dias_administrativos')
    fecha          = models.DateField()
    tipo_jornada   = models.CharField(max_length=10, choices=TIPO_JORNADA,
                                      default='COMPLETO')
    motivo         = models.TextField(blank=True)
    estado         = models.CharField(max_length=15, choices=ESTADO_CHOICES,
                                      default='PENDIENTE')
    fecha_solicitud= models.DateTimeField(auto_now_add=True)
    comentario_rrhh= models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name        = "Día administrativo"
        verbose_name_plural = "Días administrativos"
        ordering            = ['-fecha']

    def __str__(self):
        return f"{self.trabajador.get_full_name()} — {self.fecha} ({self.estado})"


# ══════════════════════════════════════════════════════════════
# LOG DE ALERTAS (evitar spam de emails)
# ══════════════════════════════════════════════════════════════

class LogAlerta(models.Model):
    TIPO_CHOICES = [
        ('AUSENCIA',     'Ausencia injustificada'),
        ('EXCESO_HORAS', 'Exceso de jornada (+2h)'),
        ('SIN_SALIDA',   'Sin marca de salida'),
    ]

    trabajador = models.ForeignKey(User, on_delete=models.CASCADE)
    empresa    = models.ForeignKey(Empresa, on_delete=models.CASCADE,
                                   null=True, blank=True)
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES)
    fecha      = models.DateField()
    enviado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Log de alerta"
        verbose_name_plural = "Logs de alertas"
        unique_together     = ('trabajador', 'tipo', 'fecha')
        ordering            = ['-enviado_en']

    def __str__(self):
        return f"{self.tipo} — {self.trabajador.get_full_name()} — {self.fecha}"