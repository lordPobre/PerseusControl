from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from apps.asistencia.views.auth import ServiceWorkerView

from django.http import JsonResponse
from django.conf import settings as django_settings

def diagnostico_cloudinary(request):
    """Endpoint temporal para verificar configuración de Cloudinary."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    return JsonResponse({
        'cloud_name':    django_settings.CLOUDINARY_CLOUD_NAME,
        'api_key':       django_settings.CLOUDINARY_API_KEY[:6] + '...' if django_settings.CLOUDINARY_API_KEY else '',
        'storage':       django_settings.DEFAULT_FILE_STORAGE,
        'media_url':     django_settings.MEDIA_URL,
        'tiene_creds':   bool(django_settings.CLOUDINARY_CLOUD_NAME and django_settings.CLOUDINARY_API_KEY),
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('diagnostico-cloudinary/', diagnostico_cloudinary, name='diagnostico_cloudinary'),
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
