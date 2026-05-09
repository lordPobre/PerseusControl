"""Perseus v4 — diagnostico_r2.py"""
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings


class Command(BaseCommand):
    help = 'Diagnostica conexión con Cloudflare R2'

    def handle(self, *args, **kwargs):
        self.stdout.write('=== DIAGNÓSTICO R2 ===')
        self.stdout.write(f'Storage: {settings.DEFAULT_FILE_STORAGE}')
        self.stdout.write(f'Media URL: {settings.MEDIA_URL}')
        self.stdout.write(f'Endpoint: {getattr(settings, "AWS_S3_ENDPOINT_URL", "NO CONFIGURADO")}')
        self.stdout.write(f'Bucket: {getattr(settings, "AWS_STORAGE_BUCKET_NAME", "NO CONFIGURADO")}')
        self.stdout.write(f'ACL: {getattr(settings, "AWS_DEFAULT_ACL", "NO CONFIGURADO")}')

        # Test subida directa con boto3
        try:
            import boto3
            s3 = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name='auto',
            )
            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key='diagnostico/test.txt',
                Body=b'Perseus test',
                ContentType='text/plain',
            )
            self.stdout.write(self.style.SUCCESS('boto3 directo: EXITOSO'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'boto3 directo: ERROR — {e}'))

        # Test subida via Django storage
        try:
            from django.core.files.storage import default_storage
            path = default_storage.save(
                'diagnostico/test_django.txt',
                ContentFile(b'Perseus Django storage test')
            )
            url = default_storage.url(path)
            self.stdout.write(self.style.SUCCESS(f'Django storage: EXITOSO — {url}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Django storage: ERROR — {e}'))
