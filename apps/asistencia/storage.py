"""
Perseus v4 — storage.py
Backend de almacenamiento personalizado usando Cloudinary SDK.
No depende de django-cloudinary-storage.
"""
import io
import logging
from django.core.files.storage import Storage
from django.conf import settings

logger = logging.getLogger(__name__)


class CloudinaryStorage(Storage):
    """
    Storage personalizado que sube archivos directamente a Cloudinary
    usando el SDK oficial, sin django-cloudinary-storage.
    """

    def _upload(self, name, content):
        """Sube un archivo a Cloudinary y retorna la URL segura."""
        import cloudinary.uploader

        # Leer contenido
        if hasattr(content, 'read'):
            data = content.read()
        else:
            data = content

        # Determinar carpeta desde el nombre
        folder = '/'.join(name.split('/')[:-1]) if '/' in name else 'perseus'
        public_id = name.replace('/', '_').rsplit('.', 1)[0]

        resultado = cloudinary.uploader.upload(
            data,
            folder        = f'perseus/{folder}',
            public_id     = public_id,
            resource_type = 'auto',
            overwrite     = True,
        )
        return resultado.get('secure_url', '')

    def _save(self, name, content):
        """Guarda el archivo en Cloudinary y retorna la URL como nombre."""
        try:
            url = self._upload(name, content)
            if url:
                return url
        except Exception as e:
            logger.error(f"Error subiendo a Cloudinary: {e}")
        return name

    def url(self, name):
        """Retorna la URL del archivo."""
        if name and name.startswith('http'):
            return name
        return f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/image/upload/{name}"

    def exists(self, name):
        """Cloudinary no necesita verificar existencia antes de subir."""
        return False

    def delete(self, name):
        """Eliminar archivo de Cloudinary."""
        try:
            import cloudinary.uploader
            public_id = name.rsplit('.', 1)[0] if '.' in name else name
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            logger.warning(f"Error eliminando de Cloudinary: {e}")

    def size(self, name):
        return 0

    def path(self, name):
        raise NotImplementedError("CloudinaryStorage no soporta paths locales.")
