from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from apps.asistencia.views.auth import ServiceWorkerView

from django.http import JsonResponse
from django.conf import settings as django_settings

def diagnostico_r2(request):
    """Endpoint temporal para verificar configuración R2."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    # Intentar subir archivo de prueba a R2
    resultado = {'config': {}, 'test_upload': 'no_intentado'}
    
    resultado['config'] = {
        'storage':    django_settings.DEFAULT_FILE_STORAGE,
        'media_url':  django_settings.MEDIA_URL,
        'bucket':     getattr(django_settings, 'AWS_STORAGE_BUCKET_NAME', ''),
        'endpoint':   getattr(django_settings, 'AWS_S3_ENDPOINT_URL', ''),
        'access_key': getattr(django_settings, 'AWS_ACCESS_KEY_ID', '')[:6] + '...' if getattr(django_settings, 'AWS_ACCESS_KEY_ID', '') else '',
    }
    
    # Test de subida
    try:
        import boto3
        from botocore.exceptions import ClientError
        s3 = boto3.client(
            's3',
            endpoint_url          = django_settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id     = django_settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key = django_settings.AWS_SECRET_ACCESS_KEY,
            region_name           = 'auto',
        )
        s3.put_object(
            Bucket      = django_settings.AWS_STORAGE_BUCKET_NAME,
            Key         = 'test/diagnostico.txt',
            Body        = b'Perseus R2 test OK',
            ContentType = 'text/plain',
        )
        resultado['test_upload'] = 'EXITOSO'
        resultado['url_prueba']  = f"{django_settings.MEDIA_URL}test/diagnostico.txt"
    except Exception as e:
        resultado['test_upload'] = f'ERROR: {str(e)}'
    
    return JsonResponse(resultado)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('diagnostico-r2/', diagnostico_r2, name='diagnostico_r2'),
    path('sw.js', ServiceWorkerView.as_view(), name='sw_js'),
    path('accounts/login/',
         auth_views.LoginView.as_view(template_name='registration/login.html'),
         name='login'),
    path('accounts/logout/',
         auth_views.LogoutView.as_view(next_page='login'),
         name='logout'),
    path('', include('apps.asistencia.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)